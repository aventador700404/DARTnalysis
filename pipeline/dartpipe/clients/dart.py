"""OpenDART API 클라이언트.

엔드포인트 이름과 응답 필드는 OpenDART 개발가이드(opendart.fss.or.kr/guide) 기준.
응답 status 코드: 000 정상, 013 조회된 데이터 없음, 020 요청 제한 초과, 901 키 만료 등.
"""

from __future__ import annotations

import hashlib
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterator

import requests

from .http import Throttle, UsageMeter, make_session

BASE_URL = "https://opendart.fss.or.kr/api"

#: 보고서 코드 (단일회사 전체 재무제표 등)
REPRT_Q1 = "11013"
REPRT_H1 = "11012"
REPRT_Q3 = "11014"
REPRT_ANNUAL = "11011"
REPORT_CODES = (REPRT_Q1, REPRT_H1, REPRT_Q3, REPRT_ANNUAL)

#: 주요사항보고서 엔드포인트 (공시 세부 유형 → API)
MAJOR_REPORT_ENDPOINTS = {
    "rights_offering": "piicDecsn",  # 유상증자 결정
    "bonus_issue": "fricDecsn",  # 무상증자 결정
    "capital_reduction": "crDecsn",  # 감자 결정
    "cb": "cvbdIsDecsn",  # 전환사채권 발행결정
    "bw": "bdwtIsDecsn",  # 신주인수권부사채권 발행결정
    "eb": "exbdIsDecsn",  # 교환사채권 발행결정
    "buyback": "tsstkAqDecsn",  # 자기주식 취득 결정
    "treasury_disposal": "tsstkDpDecsn",  # 자기주식 처분 결정
}

STATUS_OK = "000"
STATUS_NO_DATA = "013"


class DartError(RuntimeError):
    def __init__(self, status: str, message: str, endpoint: str):
        hint = {
            "010": "등록되지 않은 키입니다. DART_API_KEY 값을 확인하세요.",
            "011": "사용할 수 없는 키입니다 (일시 정지).",
            "020": "하루 호출 한도(2만 건)를 넘었습니다. 내일 다시 실행하세요.",
            "800": "OpenDART 시스템 점검 중입니다 (공휴일·주말에 잦음). 점검이 끝난 뒤 다시 실행하세요.",
            "901": "계정의 개인정보 보유기간이 만료돼 키가 막혔습니다. OpenDART에서 계정을 갱신하세요.",
        }.get(status, "")
        super().__init__(f"[DART {status}] {endpoint}: {message} {hint}".strip())
        self.status = status


class DartClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        usage: UsageMeter | None = None,
        min_interval: float = 0.15,
        cache_dir: Path | None = None,
    ):
        self.api_key = api_key
        self.session = session or make_session()
        self.usage = usage or UsageMeter()
        self.throttle = Throttle(min_interval)
        self.cache_dir = cache_dir

    # ── 내부 ──────────────────────────────────────────────
    def _cache_path(self, endpoint: str, params: dict) -> Path | None:
        if not self.cache_dir:
            return None
        key = json.dumps({"e": endpoint, **params}, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha1(key.encode()).hexdigest()[:20]
        return self.cache_dir / endpoint / f"{digest}.json"

    def get_json(self, endpoint: str, cache: bool = False, **params: Any) -> dict:
        """JSON 엔드포인트 호출. 데이터 없음(013)은 빈 list로 돌려준다."""
        params = {k: v for k, v in params.items() if v is not None}
        path = self._cache_path(endpoint, params) if cache else None
        if path and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

        self.usage.hit("dart")
        self.throttle.wait()
        resp = self.session.get(
            f"{BASE_URL}/{endpoint}.json",
            params={"crtfc_key": self.api_key, **params},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status", ""))
        if status == STATUS_NO_DATA:
            data = {"status": status, "list": []}
        elif status != STATUS_OK:
            raise DartError(status, data.get("message", ""), endpoint)

        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # ── 공시정보 ───────────────────────────────────────────
    def corp_codes(self) -> list[dict]:
        """전체 회사 고유번호 목록 (zip 안의 CORPCODE.xml)."""
        self.usage.hit("dart")
        self.throttle.wait()
        resp = self.session.get(f"{BASE_URL}/corpCode.xml", params={"crtfc_key": self.api_key}, timeout=60)
        resp.raise_for_status()
        if not resp.content.startswith(b"PK"):  # 오류는 zip 대신 <result><status>…</status> XML로 옴
            root = ET.fromstring(resp.content)
            raise DartError(root.findtext("status", ""), (root.findtext("message") or "").strip(), "corpCode")
        return parse_corp_code_zip(resp.content)

    def list_disclosures(
        self,
        bgn_de: str,
        end_de: str,
        corp_cls: str | None = "Y",
        corp_code: str | None = None,
        page_no: int = 1,
        page_count: int = 100,
        pblntf_ty: str | None = None,
    ) -> dict:
        """공시검색. corp_cls Y=유가증권(코스피). pblntf_ty A=정기공시. 회사 미지정 시 검색기간은 최대 3개월."""
        return self.get_json(
            "list",
            bgn_de=bgn_de,
            end_de=end_de,
            corp_cls=corp_cls,
            corp_code=corp_code,
            pblntf_ty=pblntf_ty,
            page_no=page_no,
            page_count=page_count,
        )

    def iter_disclosures(self, bgn_de: str, end_de: str, **kwargs: Any) -> Iterator[dict]:
        page = 1
        while True:
            data = self.list_disclosures(bgn_de, end_de, page_no=page, **kwargs)
            yield from data.get("list", [])
            total_page = int(data.get("total_page") or 1)
            if page >= total_page:
                return
            page += 1

    def company(self, corp_code: str) -> dict:
        return self.get_json("company", corp_code=corp_code)

    # ── 정기보고서 재무정보 ─────────────────────────────────
    def financial_statements(self, corp_code: str, year: int, reprt_code: str, fs_div: str = "CFS") -> list[dict]:
        """단일회사 전체 재무제표. fs_div CFS=연결, OFS=별도. 지난 기간은 캐시."""
        data = self.get_json(
            "fnlttSinglAcntAll",
            cache=True,
            corp_code=corp_code,
            bsns_year=str(year),
            reprt_code=reprt_code,
            fs_div=fs_div,
        )
        return data.get("list", [])

    def financial_statements_any(self, corp_code: str, year: int, reprt_code: str, prefer: str = "CFS") -> tuple[str, list[dict]]:
        """연결(CFS) 우선, 없으면 별도(OFS). prefer="OFS"면 별도부터 (자회사 없는 회사는 호출 절반)."""
        order = ("OFS", "CFS") if prefer == "OFS" else ("CFS", "OFS")
        for fs_div in order:
            rows = self.financial_statements(corp_code, year, reprt_code, fs_div)
            if rows:
                return fs_div, rows
        return order[-1], []

    # ── 정기보고서 주요정보 ─────────────────────────────────
    def stock_totals(self, corp_code: str, year: int, reprt_code: str) -> list[dict]:
        return self.get_json("stockTotqySttus", cache=True, corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code).get("list", [])

    def dividends(self, corp_code: str, year: int, reprt_code: str = REPRT_ANNUAL) -> list[dict]:
        return self.get_json("alotMatter", cache=True, corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code).get("list", [])

    def audit_opinion(self, corp_code: str, year: int, reprt_code: str = REPRT_ANNUAL) -> list[dict]:
        return self.get_json(
            "accnutAdtorNmNdAdtOpinion", cache=True, corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code
        ).get("list", [])

    # ── 주요사항보고서 · 지분공시 ───────────────────────────
    def major_report(self, kind: str, corp_code: str, bgn_de: str, end_de: str) -> list[dict]:
        endpoint = MAJOR_REPORT_ENDPOINTS[kind]
        return self.get_json(endpoint, corp_code=corp_code, bgn_de=bgn_de, end_de=end_de).get("list", [])

    def major_holders(self, corp_code: str) -> list[dict]:
        """대량보유 상황보고 (5% 룰)."""
        return self.get_json("majorstock", corp_code=corp_code).get("list", [])

    def insider_holdings(self, corp_code: str) -> list[dict]:
        """임원·주요주주 소유보고."""
        return self.get_json("elestock", corp_code=corp_code).get("list", [])


def parse_corp_code_zip(content: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
        root = ET.fromstring(zf.read(name))
    out = []
    for item in root.iter("list"):
        row = {child.tag: (child.text or "").strip() for child in item}
        out.append(row)
    return out


def dart_viewer_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
