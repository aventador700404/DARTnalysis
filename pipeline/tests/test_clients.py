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
def test_naver_strips_html():
    responses.get(NEWS_URL, json={"items": [{"title": "<b>가상전자</b> &quot;자사주&quot;", "description": "요약", "originallink": "https://example.com/a", "pubDate": "Tue, 29 Sep 2026 16:10:00 +0900"}]})
    items = NaverClient("id", "secret", min_interval=0).search_news("가상전자")
    assert items[0]["title"] == '가상전자 "자사주"'
    assert items[0]["published_at"].startswith("2026-09-29T16:10")
