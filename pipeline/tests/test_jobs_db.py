"""백필 작업을 진짜 Postgres(로컬 임시 DB)에 대고 끝까지 돌려보는 통합 테스트.

외부 API는 가짜 클라이언트로 대체 (응답 모양은 OpenDART·공공데이터포털 형식 그대로).
pgserver 패키지가 없으면 건너뜀:  pip install pgserver
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

pgserver = pytest.importorskip("pgserver")

from dartpipe.clients.http import UsageMeter  # noqa: E402
from dartpipe.jobs import backfill  # noqa: E402
from dartpipe.mock.generate import SPECS, Generator  # noqa: E402
from dartpipe.store import PgStore  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
AS_OF = date(2026, 9, 30)
SPEC = {s.code: s for s in SPECS[:6]}


class FakeGokr:
    def __init__(self, cal):
        self.cal = cal
        self.usage = UsageMeter()

    def _items(self, begin, end):
        for d in self.cal:
            if not (begin <= d.strftime("%Y%m%d") < end):
                continue
            for i, s in enumerate(SPEC.values()):
                px = 10_000 + i * 1000 + (hash((s.code, d)) % 300)
                yield {"basDt": d.strftime("%Y%m%d"), "srtnCd": s.code, "itmsNm": s.name, "mkp": px, "hipr": px, "lopr": px, "clpr": px, "trqu": 1000, "mrktTotAmt": px * s.shares, "lstgStCnt": s.shares}

    def stock_prices(self, bas_dt=None, begin_bas_dt=None, end_bas_dt=None, market="KOSPI", **_):
        if bas_dt:
            yield from self._items(bas_dt, (pd.Timestamp(bas_dt) + timedelta(days=1)).strftime("%Y%m%d"))
        else:
            yield from self._items(begin_bas_dt, end_bas_dt)

    def index_prices(self, name, begin_bas_dt=None, end_bas_dt=None):
        for k, d in enumerate(self.cal):
            if begin_bas_dt <= d.strftime("%Y%m%d") < end_bas_dt:
                yield {"basDt": d.strftime("%Y%m%d"), "idxNm": "코스피", "clpr": 2500 + k}


class FakeDart:
    def __init__(self):
        self.gen = Generator(seed=3)
        self.usage = UsageMeter()

    def corp_codes(self):
        return [{"corp_code": f"C{c}", "corp_name": s.name, "stock_code": c} for c, s in SPEC.items()] + [{"corp_code": "C999", "corp_name": "비상장", "stock_code": ""}]

    def company(self, corp_code):
        return {"stock_name": SPEC[corp_code[1:]].name, "induty_code": SPEC[corp_code[1:]].ksic + "11"}

    def iter_disclosures(self, bgn, end, corp_cls="Y"):
        for i, c in enumerate(SPEC):
            d = (pd.Timestamp(bgn) + timedelta(days=10 + i)).strftime("%Y%m%d")
            if d <= end:
                yield {"rcept_no": f"{d}00000{i}", "corp_code": f"C{c}", "corp_name": SPEC[c].name, "stock_code": c, "report_nm": "주요사항보고서(자기주식취득결정)", "rcept_dt": d}

    def major_report(self, kind, corp_code, bgn, end):
        code = corp_code[1:]
        i = list(SPEC).index(code)
        return [{"rcept_no": f"{bgn}00000{i}", "aqpln_stk_ostk": "1000000", "aqpln_prc_ostk": "10000000000"}]

    def major_holders(self, corp_code):
        return []

    def insider_holdings(self, corp_code):
        return []

    def financial_statements_any(self, corp_code, year, rc, prefer="CFS"):
        rows = self.gen.dart_rows(self.gen.truth(SPEC[corp_code[1:]]), year).get(rc, [])
        no = f"{year + (1 if rc == '11011' else 0)}0315000000"
        return "CFS", [{**r, "rcept_no": no} for r in rows]

    def dividends(self, corp_code, year):
        return [{"se": "현금배당금총액(백만원)", "thstrm": "12,345"}]

    def audit_opinion(self, corp_code, year):
        return [{"adt_opinion": "적정"}]


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    srv = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
    srv.psql("create role anon; create role authenticated;")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if "realtime" not in f.name:  # supabase_realtime publication은 Supabase에만 있음
            srv.psql(f.read_text())
    yield PgStore(srv.get_uri())


def test_backfill_end_to_end(store):
    cal = pd.bdate_range(AS_OF - timedelta(days=420), AS_OF)
    backfill.run(FakeDart(), FakeGokr(cal), None, store, years=1, limit=None, as_of=AS_OF, usage=UsageMeter())

    n = lambda t: int(store.read_df(f"select count(*) as n from {t}")["n"].iloc[0])  # noqa: E731
    assert n("companies") == 6
    assert n("prices_daily") > 6 * 250
    assert n("financials") >= 6 * 8
    assert n("disclosures") >= 6
    assert n("disclosure_impacts") == n("disclosures")
    assert n("scores") == 6 and n("valuation") == 6

    imp = store.read_df("select impact from disclosure_impacts where impact is not null")
    assert len(imp) >= 1 and imp["impact"].iloc[0]["kind"] == "buyback"
    ew = store.read_df("select kospi, kospi_ew from index_daily order by date limit 1")
    assert float(ew["kospi_ew"].iloc[0]) == 100.0

    # 다시 실행해도 중복 없이 갱신되는지 (멱등성), 처음 발견 시각은 유지
    seen_before = store.read_df("select rcept_no, first_seen_at from disclosures order by rcept_no")
    backfill.run(FakeDart(), FakeGokr(cal), None, store, years=1, limit=None, as_of=AS_OF, usage=UsageMeter())
    seen_after = store.read_df("select rcept_no, first_seen_at from disclosures order by rcept_no")
    assert seen_before.equals(seen_after)

    # Edge Function이 쓰는 호출 수 누적 함수
    store.read_df("select public.bump_api_usage('2026-09-30', 'dart', 3)")
    store.read_df("select public.bump_api_usage('2026-09-30', 'dart', 2)")
    assert int(store.read_df("select calls from api_usage where api = 'dart'")["calls"].iloc[0]) == 5
