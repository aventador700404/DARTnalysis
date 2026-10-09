import io
import zipfile

import pytest
import responses

from dartpipe.clients.dart import BASE_URL, DartClient, DartError, parse_corp_code_zip
from dartpipe.clients.datagokr import STOCK_URL, DataGoKrClient, DataGoKrError, portal_error_message, to_price_row
from dartpipe.clients.http import BudgetExceeded, UsageMeter
from dartpipe.clients.naver import NEWS_URL, NaverClient


@responses.activate
def test_dart_status_handling_and_pagination():
    responses.get(f"{BASE_URL}/list.json", json={"status": "000", "total_page": 2, "list": [{"rcept_no": "1"}]})
    responses.get(f"{BASE_URL}/list.json", json={"status": "000", "total_page": 2, "list": [{"rcept_no": "2"}]})
    c = DartClient("k" * 40, min_interval=0)
    got = [r["rcept_no"] for r in c.iter_disclosures("20260101", "20260131")]
    assert got == ["1", "2"]
    assert c.usage.counts["dart"] == 2


@responses.activate
def test_dart_no_data_and_errors():
    responses.get(f"{BASE_URL}/piicDecsn.json", json={"status": "013", "message": "조회된 데이타가 없습니다."})
    responses.get(f"{BASE_URL}/company.json", json={"status": "020", "message": "요청 제한을 초과하였습니다."})
    c = DartClient("k" * 40, min_interval=0)
    assert c.major_report("rights_offering", "00126380", "20250101", "20251231") == []
    with pytest.raises(DartError) as e:
        c.company("00126380")
    assert e.value.status == "020" and "내일" in str(e.value)


@responses.activate
def test_dart_cache_avoids_second_call(tmp_path):
    responses.get(f"{BASE_URL}/fnlttSinglAcntAll.json", json={"status": "000", "list": [{"account_id": "x"}]})
    c = DartClient("k" * 40, min_interval=0, cache_dir=tmp_path)
    c.financial_statements("00126380", 2025, "11011")
    c.financial_statements("00126380", 2025, "11011")
    assert len(responses.calls) == 1


def test_budget_guard():
    m = UsageMeter(budgets={"dart": 2})
    m.hit("dart")
    m.hit("dart")
    with pytest.raises(BudgetExceeded):
        m.hit("dart")


@responses.activate
def test_corp_code_error_is_readable():
    """corpCode는 오류일 때 zip 대신 XML을 줌 → 'BadZipFile' 대신 DART 상태·이유를 보여준다."""
    xml = '<?xml version="1.0" encoding="UTF-8"?><result><status>800</status><message>시스템 점검으로 인한  서비스가 중지 중입니다.</message></result>'
    responses.get(f"{BASE_URL}/corpCode.xml", body=xml, content_type="application/xml")
    with pytest.raises(DartError) as e:
        DartClient("k" * 40, min_interval=0).corp_codes()
    assert e.value.status == "800" and "점검" in str(e.value)


def test_corp_code_zip():
    xml = "<result><list><corp_code>00126380</corp_code><corp_name>가상전자</corp_name><stock_code>005930</stock_code></list></result>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", xml)
    assert parse_corp_code_zip(buf.getvalue()) == [{"corp_code": "00126380", "corp_name": "가상전자", "stock_code": "005930"}]


@responses.activate
def test_datagokr_pagination_and_row():
    item = {"basDt": "20260929", "srtnCd": "005930", "itmsNm": "가상", "mkp": "100", "hipr": "110", "lopr": "90", "clpr": "105", "trqu": "1000", "mrktTotAmt": "1050000", "lstgStCnt": "10000"}
    body = lambda total: {"response": {"header": {"resultCode": "00"}, "body": {"totalCount": total, "items": {"item": [item]}}}}
    responses.get(STOCK_URL, json=body(2))
    responses.get(STOCK_URL, json=body(2))
    c = DataGoKrClient("key", min_interval=0)
    rows = list(c.stock_prices(bas_dt="20260929", num_rows=1))
    assert len(rows) == 2
    r = to_price_row(rows[0])
    assert r["date"] == "2026-09-29" and r["close"] == 105 and r["shares"] == 10000


@responses.activate
def test_datagokr_portal_error_is_readable():
    """키 미등록 오류는 403 + JSON(또는 XML)으로 옴 → 'Forbidden' 대신 포털의 이유를 보여준다."""
    err_json = {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "returnAuthMsg": "등록되지 않은 서비스키", "returnReasonCode": "30"}}}
    responses.get(STOCK_URL, json=err_json, status=403)
    with pytest.raises(DataGoKrError, match="SERVICE_KEY_IS_NOT_REGISTERED_ERROR.*등록되지 않은 서비스키"):
        list(DataGoKrClient("key", min_interval=0).stock_prices(bas_dt="20260929"))
    err_xml = "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg><returnAuthMsg>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    msg = portal_error_message(err_xml)
    assert msg.startswith("[공공데이터포털 LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR]") and "한도" in msg
    assert portal_error_message('{"response": {"header": {"resultCode": "00"}}}') is None


@responses.activate
def test_datagokr_via_seoul_relay():
    """중계 모드: 서비스키는 보내지 않고, svc·비밀 헤더·서울 리전 헤더를 붙여 중계 주소로 보낸다."""
    relay = "https://ref.supabase.co/functions/v1/datagokr-relay"
    item = {"basDt": "20260929", "srtnCd": "005930", "clpr": "105"}
    responses.get(relay, json={"response": {"header": {"resultCode": "00"}, "body": {"totalCount": 1, "items": {"item": [item]}}}})
    c = DataGoKrClient(None, min_interval=0, relay_url=relay, relay_secret="s3cret")
    assert list(c.stock_prices(bas_dt="20260929"))[0]["clpr"] == "105"
    req = responses.calls[0].request
    assert "svc=stock" in req.url and "serviceKey" not in req.url and "basDt=20260929" in req.url
    assert req.headers["x-relay-secret"] == "s3cret" and req.headers["x-region"] == "ap-northeast-2"

    responses.get(relay, json={"error": "unauthorized"}, status=401)
    with pytest.raises(DataGoKrError, match="서울 중계 오류 401"):
        list(c.index_prices("코스피"))
    with pytest.raises(ValueError):
        DataGoKrClient(None)


@responses.activate
def test_naver_strips_html():
    responses.get(NEWS_URL, json={"items": [{"title": "<b>가상전자</b> &quot;자사주&quot;", "description": "요약", "originallink": "https://example.com/a", "pubDate": "Tue, 29 Sep 2026 16:10:00 +0900"}]})
    items = NaverClient("id", "secret", min_interval=0).search_news("가상전자")
    assert items[0]["title"] == '가상전자 "자사주"'
    assert items[0]["published_at"].startswith("2026-09-29T16:10")


def test_relay_resolved_from_supabase_db_url():
    """GitHub Actions에선 SUPABASE_DB_URL만으로 중계 주소·비밀값을 찾는다 (사람이 비밀번호를 만들 필요 없음)."""
    import pandas as pd

    from dartpipe.config import Settings
    from dartpipe.jobs.common import make_datagokr, supabase_ref

    assert supabase_ref("postgresql://postgres.abcref:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres") == "abcref"
    assert supabase_ref("postgresql://postgres:pw@db.abcref.supabase.co:5432/postgres") == "abcref"
    assert supabase_ref("postgresql://u:p@localhost:5432/x") is None

    def settings(**kw):
        base = dict(dart_api_key=None, datagokr_service_key=None, datagokr_relay_url=None, datagokr_relay_secret=None,
                    naver_client_id=None, naver_client_secret=None, supabase_db_url=None, dart_daily_budget=1)
        return Settings(**{**base, **kw})

    class VaultStore:
        def read_df(self, sql, params=None):
            return pd.DataFrame({"s": ["vault-secret"]})

    class NoFnStore:
        def read_df(self, sql, params=None):
            raise RuntimeError("function does not exist")

    db = "postgresql://postgres.abcref:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
    c = make_datagokr(settings(supabase_db_url=db), VaultStore(), None)
    assert c.relay_url == "https://abcref.supabase.co/functions/v1/datagokr-relay" and c.relay_secret == "vault-secret"
    # 중계 함수가 없는 DB → 서비스키로 직접 접속
    c = make_datagokr(settings(supabase_db_url=db, datagokr_service_key="k"), NoFnStore(), None)
    assert c.relay_url is None and c.service_key == "k"
    with pytest.raises(RuntimeError):
        make_datagokr(settings(), NoFnStore(), None)


def test_portal_key_accepts_encoding_or_decoding():
    from dartpipe.config import _portal_key

    assert _portal_key(" abc+/de==\n") == "abc+/de=="
    assert _portal_key("abc%2B%2Fde%3D%3D") == "abc+/de=="
    assert _portal_key("a1b2c3") == "a1b2c3" and _portal_key("  ") is None


def test_to_price_row_matches_real_v2_response():
    """2026-10-07 V2 실제 응답 1건 (필드명·문자열 숫자 형식 확인용)."""
    item = {"basDt": "20261007", "srtnCd": "000020", "isinCd": "KR7000020008", "itmsNm": "동화약품", "mrktCtg": "KOSPI",
            "clpr": "5610", "vs": "160", "fltRt": "2.94", "mkp": "5430", "hipr": "5950", "lopr": "5360", "trqu": "2421088",
            "trPrc": "13732062195", "lstgStCnt": "27931470", "mrktTotAmt": "156695546700"}
    assert "_V2/" in STOCK_URL
    assert to_price_row(item) == {"date": "2026-10-07", "code": "000020", "name": "동화약품", "open": 5430, "high": 5950,
                                  "low": 5360, "close": 5610, "volume": 2421088, "market_cap": 156695546700, "shares": 27931470}


def test_corp_codes_fall_back_to_periodic_reports():
    """corpCode 파일이 점검으로 막혀도 최근 정기공시 목록으로 종목코드→고유번호를 만든다."""
    from datetime import date

    from dartpipe.jobs.common import corp_codes_by_stock

    class MaintDart:
        calls = []

        def corp_codes(self):
            raise DartError("800", "시스템 점검", "corpCode")

        def iter_disclosures(self, bgn, end, **kw):
            self.calls.append((bgn, end, kw))
            if len(self.calls) == 1:
                yield {"corp_code": "00126380", "corp_name": "가상전자", "stock_code": "005930", "report_nm": "반기보고서"}
                yield {"corp_code": "00999999", "corp_name": "비상장", "stock_code": " "}
            else:
                yield {"corp_code": "00164779", "corp_name": "가상화학", "stock_code": "000660", "report_nm": "사업보고서"}

    d = MaintDart()
    got = corp_codes_by_stock(d, date(2026, 10, 9), {"005930", "000660"})
    assert got["005930"]["corp_code"] == "00126380" and got["000660"]["corp_code"] == "00164779"
    assert len(got) == 2 and len(d.calls) == 2  # 둘 다 찾으면 더 거슬러 올라가지 않음
    assert d.calls[0] == ("20260712", "20261009", {"corp_cls": "Y", "pblntf_ty": "A"})
