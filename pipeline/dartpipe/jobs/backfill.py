"""최초 1회: 코스피 과거 데이터 채우기 (명세서 7장 1단계).

    python -m dartpipe.jobs.backfill --years 5           # 전체
    python -m dartpipe.jobs.backfill --years 1 --limit 20 # 시험 삼아 20개 종목만

DART 하루 한도(2만 건) 때문에 전체 백필은 이틀 이상 걸릴 수 있다.
재무 응답은 pipeline/.cache/ 에 저장되므로, 한도에 걸려 멈추면 다음 날 같은 명령을 다시 실행하면 이어서 진행된다.
"""

from __future__ import annotations

import argparse
import logging
from datetime import timedelta

from ..clients.dart import DartClient
from ..clients.http import BudgetExceeded, UsageMeter
from ..clients.naver import NaverClient
from ..config import REPO_ROOT, get_settings, require
from ..store import PgStore
from . import common

log = logging.getLogger("dartpipe")


def run(dart, gokr, naver, store, years: int, limit: int | None, as_of, usage: UsageMeter, workers: int = 1) -> None:
    begin = as_of - timedelta(days=365 * years)
    companies = common.refresh_companies(dart, gokr, store, as_of, limit=limit, workers=workers)
    codes = {c["code"] for c in companies}
    common.load_index(gokr, store, begin, as_of + timedelta(days=1))
    common.load_prices(gokr, store, begin, as_of + timedelta(days=1), codes)
    disclosures = common.load_disclosures(dart, store, begin, as_of, codes, workers=workers)
    common.attach_details(dart, store, disclosures, workers=workers)

    # 재무: 3년 성장률 + TTM 계산을 위해 (years + 1)년치. 회사별로 동시에 (DB 쓰기는 store가 순서대로 처리)
    fin_years = list(range(as_of.year - years - 1, as_of.year + 1))
    done = [0]

    def load_company(c: dict) -> None:
        common.load_financials(dart, store, c["corp_code"], c["code"], fin_years, as_of)
        common.load_annual_facts(dart, store, c["corp_code"], c["code"], as_of.year - 1)
        done[0] += 1
        if done[0] % 50 == 0:
            log.info("재무 진행: %d / %d (DART %d회)", done[0], len(companies), usage.counts["dart"])

    common.pmap(load_company, companies, workers)

    if naver is not None:
        recent = [d for d in disclosures if d["rcept_dt"] >= (as_of - timedelta(days=30)).isoformat()]
        common.attach_news(naver, store, recent, {c["code"]: c["name"] for c in companies})

    common.recompute(store, as_of, years)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="코스피 과거 데이터 백필")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None, help="앞에서부터 N개 종목만 (시험용)")
    args = ap.parse_args()

    s = get_settings()
    usage = UsageMeter(budgets={"dart": s.dart_daily_budget})
    dart = DartClient(require(s.dart_api_key, "DART_API_KEY"), usage=usage, cache_dir=REPO_ROOT / "pipeline" / ".cache" / "dart")
    store = PgStore(require(s.supabase_db_url, "SUPABASE_DB_URL"))
    gokr = common.make_datagokr(s, store, usage)
    naver = NaverClient(s.naver_client_id, s.naver_client_secret, usage=usage) if s.naver_client_id and s.naver_client_secret else None
    as_of = common.today_kst()
    try:
        run(dart, gokr, naver, store, args.years, args.limit, as_of, usage, workers=s.dart_workers)
    except BudgetExceeded as e:
        log.warning(str(e))
    finally:
        store.upsert("api_usage", usage.as_rows(as_of.isoformat()))
        log.info("API 호출 수: %s", dict(usage.counts))


if __name__ == "__main__":
    main()
