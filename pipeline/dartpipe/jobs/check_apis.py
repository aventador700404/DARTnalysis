"""API 키가 제대로 동작하는지 한 번씩만 호출해보는 점검 스크립트 (DB 불필요).

    python -m dartpipe.jobs.check_apis

각 API에서 응답 1~2건을 받아 핵심 필드가 있는지 출력한다. 백필 전에 먼저 실행하세요.
"""

from __future__ import annotations

from datetime import timedelta

from ..clients.dart import DartClient, REPRT_ANNUAL
from ..clients.datagokr import DataGoKrClient, to_price_row
from ..clients.naver import NaverClient
from ..config import get_settings
from .common import today_kst, ymd


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def main() -> None:
    s = get_settings()
    today = today_kst()

    print("1) OpenDART")
    if not s.dart_api_key:
        fail("DART_API_KEY 없음")
    else:
        try:
            dart = DartClient(s.dart_api_key)
            items = list(dart.list_disclosures(ymd(today - timedelta(days=7)), ymd(today), corp_cls="Y", page_count=5).get("list", []))
            ok(f"공시검색: 최근 7일 코스피 공시 예시 → {items[0]['corp_name']} / {items[0]['report_nm']}" if items else "공시검색: 응답은 정상, 결과 0건")
            sample_corp = items[0]["corp_code"] if items else "00126380"
            rows = dart.financial_statements(sample_corp, today.year - 1, REPRT_ANNUAL)
            ok(f"전체 재무제표: {len(rows)}개 계정 (예: {rows[0]['account_nm']} = {rows[0]['thstrm_amount']})" if rows else "전체 재무제표: 0건 (해당 회사·연도 보고서 없음)")
        except Exception as e:  # noqa: BLE001
            fail(str(e))

    print("2) 공공데이터포털 (금융위원회 주식시세·지수시세)")
    if not s.datagokr_service_key:
        fail("DATAGOKR_SERVICE_KEY 없음")
    else:
        try:
            gokr = DataGoKrClient(s.datagokr_service_key)
            got = None
            for back in range(1, 8):
                got = next(gokr.stock_prices(bas_dt=ymd(today - timedelta(days=back)), market="KOSPI", num_rows=1), None)
                if got:
                    break
            if got:
                r = to_price_row(got)
                ok(f"주식시세: {r['date']} {r['name']} 종가 {r['close']:,.0f} / 시총 {r['market_cap']:,.0f} / 상장주식 {r['shares']:,.0f}")
            else:
                fail("주식시세: 최근 7일 데이터 없음")
            idx = next(gokr.index_prices("코스피", begin_bas_dt=ymd(today - timedelta(days=10)), end_bas_dt=ymd(today)), None)
            ok(f"지수시세: {idx['basDt']} 코스피 {idx['clpr']}") if idx else fail("지수시세: 결과 없음")
        except Exception as e:  # noqa: BLE001
            fail(str(e))

    print("3) 네이버 검색 API")
    if not (s.naver_client_id and s.naver_client_secret):
        fail("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음 (뉴스 없이도 나머지는 동작)")
    else:
        try:
            news = NaverClient(s.naver_client_id, s.naver_client_secret).search_news("코스피", display=1)
            ok(f"뉴스: {news[0]['title']}" if news else "뉴스: 결과 0건")
        except Exception as e:  # noqa: BLE001
            fail(str(e))

    print("4) Supabase DB 연결")
    if not s.supabase_db_url:
        fail("SUPABASE_DB_URL 없음")
    else:
        try:
            from ..store import PgStore

            n = PgStore(s.supabase_db_url).read_df("select count(*) as n from companies")["n"].iloc[0]
            ok(f"연결 성공 (companies {n}행)")
        except Exception as e:  # noqa: BLE001
            fail(f"{e} — supabase/migrations/0001_init.sql 을 먼저 실행했는지 확인")


if __name__ == "__main__":
    main()
