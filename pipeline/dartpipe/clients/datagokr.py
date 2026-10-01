"""공공데이터포털 금융위원회 API 클라이언트 (일별 주가·지수, 하루 지연).

- 금융위원회_주식시세정보  : GetStockSecuritiesInfoService/getStockPriceInfo
- 금융위원회_지수시세정보  : GetMarketIndexInfoService/getStockMarketIndex

주의: 응답 필드명은 활용가이드 기준이며, 포털 사정으로 바뀔 수 있으니 처음 실행할 때
`python -m dartpipe.jobs.check_apis` 로 응답 형태를 한 번 확인하세요.
가격은 수정주가가 아닌 실제 종가라서, 액면분할 등은 상장주식 수 변화로 감지해 분석에서 제외합니다.
"""

from __future__ import annotations

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
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:  # 인증 오류 등은 XML로 오는 경우가 있음
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
