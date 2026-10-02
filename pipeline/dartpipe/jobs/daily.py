"""매일 장 마감 후 배치 (GitHub Actions에서 실행).

1. 최근 주가·지수 (공공데이터는 하루 늦게 올라옴 → 지난 7일치를 다시 받아 빈 날 채우기)
2. 최근 3일 공시 다시 확인 (실시간 수집이 놓친 것 보완) + 상세 붙이기
3. 정기보고서가 새로 나온 회사만 재무 갱신
4. 전체 재계산: 공시 후 수익률, 유형별 통계, 밸류에이션, 건강검진
5. (월요일) 종목 목록·업종코드 갱신

    python -m dartpipe.jobs.daily
"""

from __future__ import annotations

import argparse
import logging
from datetime import timedelta

from ..clients.dart import DartClient
from ..clients.datagokr import DataGoKrClient
from ..clients.http import BudgetExceeded, UsageMeter
from ..clients.naver import NaverClient
from ..config import REPO_ROOT, get_settings, require
from ..store import PgStore
from . import common

log = logging.getLogger("dartpipe")


def run(dart, gokr, naver, store, as_of, weekly: bool) -> None:
    if weekly:
        companies = common.refresh_companies(dart, gokr, store, as_of)
    else:
        companies = store.read_df("select code, corp_code, name from companies").to_dict("records")
    codes = {c["code"] for c in companies}
    corp_of = {c["code"]: c["corp_code"] for c in companies}

    common.load_prices(gokr, store, as_of - timedelta(days=7), as_of + timedelta(days=1), codes)
    common.load_index(gokr, store, as_of - timedelta(days=7), as_of + timedelta(days=1))

    disclosures = common.load_disclosures(dart, store, as_of - timedelta(days=3), as_of, codes)
    pending = store.read_df(
        "select rcept_no, code, corp_code, rcept_dt, subtype from disclosures where detail is null and rcept_dt >= %(since)s",
        {"since": as_of - timedelta(days=30)},
    ).to_dict("records")
    common.attach_details(dart, store, pending)

    new_reports = {d["code"] for d in disclosures if d.get("subtype") == "periodic_report"}
    for code in sorted(new_reports):
        common.load_financials(dart, store, corp_of[code], code, [as_of.year - 1, as_of.year])
        common.load_annual_facts(dart, store, corp_of[code], code, as_of.year - 1)

    if naver is not None:
        common.attach_news(naver, store, disclosures, {c["code"]: c["name"] for c in companies})

    common.recompute(store, as_of)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="일일 배치")
    ap.add_argument("--weekly", action="store_true", help="종목 목록·업종코드도 갱신")
    args = ap.parse_args()

    s = get_settings()
    usage = UsageMeter(budgets={"dart": s.dart_daily_budget})
    dart = DartClient(require(s.dart_api_key, "DART_API_KEY"), usage=usage, cache_dir=REPO_ROOT / "pipeline" / ".cache" / "dart")
    gokr = DataGoKrClient(s.datagokr_service_key, usage=usage, relay_url=s.datagokr_relay_url, relay_secret=s.datagokr_relay_secret)
    naver = NaverClient(s.naver_client_id, s.naver_client_secret, usage=usage) if s.naver_client_id and s.naver_client_secret else None
    store = PgStore(require(s.supabase_db_url, "SUPABASE_DB_URL"))
    as_of = common.today_kst()
    try:
        run(dart, gokr, naver, store, as_of, weekly=args.weekly or as_of.weekday() == 0)
    except BudgetExceeded as e:
        log.warning(str(e))
    finally:
        store.upsert("api_usage", usage.as_rows(as_of.isoformat()))
        log.info("API 호출 수: %s", dict(usage.counts))


if __name__ == "__main__":
    main()
