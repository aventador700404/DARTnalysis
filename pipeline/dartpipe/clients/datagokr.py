"""공공데이터포털 금융위원회 API 클라이언트 (일별 주가·지수, 하루 지연).

- 금융위원회_주식시세정보  : GetStockSecuritiesInfoService/getStockPriceInfo
- 금융위원회_지수시세정보  : GetMarketIndexInfoService/getStockMarketIndex

주의: 응답 필드명은 활용가이드 기준이며, 포털 사정으로 바뀔 수 있으니 처음 실행할 때
`python -m dartpipe.jobs.check_apis` 로 응답 형태를 한 번 확인하세요.
가격은 수정주가가 아닌 실제 종가라서, 액면분할 등은 상장주식 수 변화로 감지해 분석에서 제외합니다.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

import requests

from .http import Throttle, UsageMeter, make_session

BASE = "https://apis.data.go.kr/1160100/service"
STOCK_URL = f"{BASE}/GetStockSecuritiesInfoService/getStockPriceInfo"
INDEX_URL = f"{BASE}/GetMarketIndexInfoService/getStockMarketIndex"


class DataGoKrError(RuntimeError):
    pass


class DataGoKrClient:
    def __init__(
        self,
        service_key: str,
        session: requests.Session | None = None,
        usage: UsageMeter | None = None,
        min_interval: float = 0.1,
    ):
        self.service_key = service_key  # "Decoding" 키 (requests가 URL 인코딩함)
        self.session = session or make_session()
        self.usage = usage or UsageMeter()
        self.throttle = Throttle(min_interval)

    def _get(self, url: str, **params: Any) -> dict:
        self.usage.hit("datagokr")
        self.throttle.wait()
        resp = self.session.get(
            url,
            params={"serviceKey": self.service_key, "resultType": "json", **{k: v for k, v in params.items() if v is not None}},
            timeout=60,
        )
        gateway_error = portal_error_message(resp.text)
        if gateway_error:  # 키 미등록 등은 403·401과 함께 별도 형식으로 옴
            raise DataGoKrError(gateway_error)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise DataGoKrError(f"JSON이 아닌 응답: {resp.text[:300]}") from exc
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") not in (None, "00"):
            raise DataGoKrError(f"{header.get('resultCode')}: {header.get('resultMsg')}")
        return data["response"]["body"]

    def _paginate(self, url: str, num_rows: int, **params: Any) -> Iterator[dict]:
        page = 1
        while True:
            body = self._get(url, numOfRows=num_rows, pageNo=page, **params)
            items = body.get("items") or {}
            rows = items.get("item", []) if isinstance(items, dict) else []
            if isinstance(rows, dict):
                rows = [rows]
            yield from rows
            total = int(body.get("totalCount") or 0)
            if page * num_rows >= total or not rows:
                return
            page += 1

    def stock_prices(
        self,
        bas_dt: str | None = None,
        begin_bas_dt: str | None = None,
        end_bas_dt: str | None = None,
        market: str = "KOSPI",
        short_code: str | None = None,
        num_rows: int = 5000,
    ) -> Iterator[dict]:
        """일별 시세. 날짜는 YYYYMMDD. endBasDt는 '미만' 조건."""
        yield from self._paginate(
            STOCK_URL,
            num_rows,
            basDt=bas_dt,
            beginBasDt=begin_bas_dt,
            endBasDt=end_bas_dt,
            mrktCls=market,
            likeSrtnCd=short_code,
        )

    def index_prices(
        self,
        index_name: str = "코스피",
        begin_bas_dt: str | None = None,
        end_bas_dt: str | None = None,
        num_rows: int = 2000,
    ) -> Iterator[dict]:
        for row in self._paginate(INDEX_URL, num_rows, idxNm=index_name, beginBasDt=begin_bas_dt, endBasDt=end_bas_dt):
            if row.get("idxNm") == index_name:  # idxNm은 부분 일치라 정확히 거르기
                yield row


#: 포털 공통 오류 코드 → 사람이 읽을 설명
_PORTAL_HINTS = {
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR": "활용신청 승인 직후라면 1~2시간 뒤 다시 시도하세요. 계속되면 Decoding 키인지, 두 서비스 모두 승인됐는지 확인.",
    "SERVICE_KEY_IS_NULL": "DATAGOKR_SERVICE_KEY 가 비어 있습니다.",
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": "하루 호출 한도를 넘었습니다. 내일 다시 실행하세요.",
    "SERVICE_ACCESS_DENIED_ERROR": "이 서비스에 대한 활용신청이 없거나 승인되지 않았습니다.",
}


def portal_error_message(text: str) -> str | None:
    """공공데이터포털 게이트웨이 오류(OpenAPI_ServiceResponse, JSON·XML 모두)를 읽어 설명으로 바꾼다."""
    if "OpenAPI_ServiceResponse" not in (text or ""):
        return None
    try:
        header = json.loads(text)["OpenAPI_ServiceResponse"]["cmmMsgHeader"]
        flat = f"{header.get('errMsg', '')} {header.get('returnAuthMsg', '')}"
        reason_s = str(header.get("returnAuthMsg", "")).strip()
    except (ValueError, KeyError, TypeError):  # XML
        flat = text
        m = re.search(r"<returnAuthMsg>([^<]*)</returnAuthMsg>", text)
        reason_s = m.group(1).strip() if m else ""
    # JSON은 errMsg에, XML은 returnAuthMsg에 코드가 들어오므로 대문자_코드 형태를 찾는다
    code = re.search(r"\b([A-Z]+(?:_[A-Z]+){2,})\b", flat)
    code_s = code.group(1) if code else "UNKNOWN"
    msg = f"[공공데이터포털 {code_s}]" + (f" {reason_s}" if reason_s and reason_s != code_s else "")
    hint = _PORTAL_HINTS.get(code_s)
    return f"{msg} — {hint}" if hint else msg


def to_price_row(item: dict) -> dict:
    """금융위 시세 응답 1건 → prices_daily 행."""

    def num(key: str) -> float | None:
        v = item.get(key)
        if v in (None, ""):
            return None
        return float(str(v).replace(",", ""))

    d = item["basDt"]
    return {
        "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
        "code": item["srtnCd"].lstrip("A"),
        "name": item.get("itmsNm"),
        "open": num("mkp"),
        "high": num("hipr"),
        "low": num("lopr"),
        "close": num("clpr"),
        "volume": num("trqu"),
        "market_cap": num("mrktTotAmt"),
        "shares": num("lstgStCnt"),
    }
