"""공시 제목(report_nm) → 차트 마커 유형 분류.

마커 유형은 5개로 고정 (색상 슬롯 순서와 1:1).
차트에서 위·아래 두 줄로 나눠 찍는다: 위 = 자금조달·자사주·기타, 아래 = 실적·지분 변동.
(한 줄 안의 색끼리는 색약·정상 시각 모두 구분되도록 검증한 조합 — web/lib/categories.ts 참고)
세부 유형(subtype)은 재무 영향 계산에 쓸 주요사항보고서 API를 고르는 데 사용.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 마커 유형 — 화면 표시 순서이자 색상 슬롯 순서. 바꾸면 web/lib/categories.ts 도 같이 바꾸기.
CATEGORIES: dict[str, str] = {
    "earnings": "실적·정기보고서",
    "financing": "자금조달 (증자·감자·CB)",
    "buyback": "자사주",
    "ownership": "지분 변동",
    "other": "기타",
}


@dataclass(frozen=True)
class Classification:
    category: str
    subtype: str | None
    is_correction: bool


_PREFIX = re.compile(r"^\[(?P<tag>[^\]]+)\]")

# (정규식, category, subtype) — 위에서부터 먼저 맞는 규칙 적용. 공백은 제거한 뒤 비교.
_RULES: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"유무상증자결정"), "financing", "rights_offering"),
    (re.compile(r"유상증자결정"), "financing", "rights_offering"),
    (re.compile(r"무상증자결정"), "financing", "bonus_issue"),
    (re.compile(r"감자결정"), "financing", "capital_reduction"),
    (re.compile(r"전환사채권발행결정"), "financing", "cb"),
    (re.compile(r"신주인수권부사채권발행결정"), "financing", "bw"),
    (re.compile(r"교환사채권발행결정"), "financing", "eb"),
    (re.compile(r"자기주식취득신탁계약"), "buyback", "buyback_trust"),
    (re.compile(r"자기주식취득결정"), "buyback", "buyback"),
    (re.compile(r"자기주식처분결정"), "buyback", "treasury_disposal"),
    (re.compile(r"자기주식소각"), "buyback", "cancellation"),
    (re.compile(r"주식등의대량보유상황보고서"), "ownership", "major_holder"),
    (re.compile(r"임원[ㆍ·]?주요주주특정증권등소유상황보고서"), "ownership", "insider"),
    (re.compile(r"최대주주변경"), "ownership", "largest_holder_change"),
    (re.compile(r"(사업|반기|분기)보고서"), "earnings", "periodic_report"),
    (re.compile(r"영업\(잠정\)실적|연결재무제표기준영업\(잠정\)실적"), "earnings", "preliminary_earnings"),
    (re.compile(r"매출액또는손익구조"), "earnings", "earnings_change"),
]


def classify(report_nm: str) -> Classification:
    name = (report_nm or "").strip()
    is_correction = False
    m = _PREFIX.match(name)
    if m:
        is_correction = "정정" in m.group("tag")
        name = name[m.end():]
    compact = re.sub(r"\s+", "", name)
    for pattern, category, subtype in _RULES:
        if pattern.search(compact):
            return Classification(category, subtype, is_correction)
    return Classification("other", None, is_correction)
