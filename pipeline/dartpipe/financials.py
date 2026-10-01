"""단일회사 전체 재무제표(fnlttSinglAcntAll) → 표준 계정 → 분기별 값.

핵심 규칙 (명세서 4.4):
- 손익계산서(IS/CIS): 1분기 보고서는 1분기 값, 반기·3분기 보고서는 '3개월 값(thstrm_amount)'과
  '누적 값(thstrm_add_amount)'을 함께 준다. 사업보고서는 연간 값만 준다.
  → 누적 값 C1..C4를 만든 뒤 차분해서 분기 값을 구한다. 4분기 = 연간 − 3분기 누적.
- 현금흐름표(CF): 분·반기 보고서도 누적 값만 주므로 같은 방식으로 차분.
- 재무상태표(BS): 분기 말 시점 값 그대로.

계정은 XBRL 표준 account_id 우선, 회사별 자체 계정이면 계정명으로 대체 매칭.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .clients.dart import REPRT_ANNUAL, REPRT_H1, REPRT_Q1, REPRT_Q3

# item: (허용 sj_div, account_id 후보, 계정명 후보)
_IS = ("IS", "CIS")
ACCOUNTS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "revenue": (_IS, ("ifrs-full_Revenue",), ("매출액", "수익(매출액)", "영업수익", "매출")),
    "operating_income": (_IS, ("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)")),
    "net_income": (_IS, ("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익")),
    "net_income_parent": (
        _IS,
        ("ifrs-full_ProfitLossAttributableToOwnersOfParent",),
        ("지배기업의 소유주에게 귀속되는 당기순이익", "지배기업 소유주지분", "지배기업소유주지분"),
    ),
    "interest_expense": (_IS, ("ifrs-full_InterestExpense", "dart_InterestExpense"), ("이자비용",)),
    "operating_cash_flow": (
        ("CF",),
        ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
        ("영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동으로인한현금흐름"),
    ),
    "total_assets": (("BS",), ("ifrs-full_Assets",), ("자산총계",)),
    "total_liabilities": (("BS",), ("ifrs-full_Liabilities",), ("부채총계",)),
    "total_equity": (("BS",), ("ifrs-full_Equity",), ("자본총계",)),
    "equity_parent": (
        ("BS",),
        ("ifrs-full_EquityAttributableToOwnersOfParent",),
        ("지배기업의 소유주에게 귀속되는 자본", "지배기업 소유주지분", "지배기업소유주지분"),
    ),
}
FLOW_ITEMS = tuple(k for k, v in ACCOUNTS.items() if v[0] != ("BS",))
STOCK_ITEMS = tuple(k for k, v in ACCOUNTS.items() if v[0] == ("BS",))
CF_ITEMS = tuple(k for k, v in ACCOUNTS.items() if v[0] == ("CF",))


def parse_amount(value: object) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


@dataclass(frozen=True)
class ReportValues:
    """보고서 1건에서 뽑은 계정별 (당기금액, 당기누적금액)."""

    amount: dict[str, float | None]
    add_amount: dict[str, float | None]


def extract_report(rows: Iterable[dict]) -> ReportValues:
    rows = list(rows)
    amount: dict[str, float | None] = {}
    add_amount: dict[str, float | None] = {}
    for item, (sj_divs, ids, names) in ACCOUNTS.items():
        candidates = [r for r in rows if r.get("sj_div") in sj_divs]
        match = next((r for r in candidates if r.get("account_id") in ids), None)
        if match is None:
            norm_names = {n.replace(" ", "") for n in names}
            match = next(
                (r for r in candidates if str(r.get("account_nm", "")).replace(" ", "") in norm_names),
                None,
            )
        amount[item] = parse_amount(match.get("thstrm_amount")) if match else None
        add_amount[item] = parse_amount(match.get("thstrm_add_amount")) if match else None
    return ReportValues(amount, add_amount)


def _sub(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def quarterize_year(reports: dict[str, ReportValues]) -> dict[int, dict[str, float | None]]:
    """한 사업연도의 보고서들(reprt_code → 값) → {분기: {계정: 값}}.

    없는 보고서는 건너뛰고, 계산할 수 없는 값은 None.
    """
    q1, h1, q3, fy = (reports.get(c) for c in (REPRT_Q1, REPRT_H1, REPRT_Q3, REPRT_ANNUAL))
    out: dict[int, dict[str, float | None]] = {}

    for item in FLOW_ITEMS:
        is_cf = item in CF_ITEMS
        # 누적 값 C1..C4
        c1 = q1.amount[item] if q1 else None
        if h1:
            c2 = h1.amount[item] if is_cf else h1.add_amount[item]
            if c2 is None and not is_cf and c1 is not None and h1.amount[item] is not None:
                c2 = c1 + h1.amount[item]
        else:
            c2 = None
        if q3:
            c3 = q3.amount[item] if is_cf else q3.add_amount[item]
            if c3 is None and not is_cf and c2 is not None and q3.amount[item] is not None:
                c3 = c2 + q3.amount[item]
        else:
            c3 = None
        c4 = fy.amount[item] if fy else None

        quarters = {
            1: c1,
            2: h1.amount[item] if (h1 and not is_cf and h1.amount[item] is not None) else _sub(c2, c1),
            3: q3.amount[item] if (q3 and not is_cf and q3.amount[item] is not None) else _sub(c3, c2),
            4: _sub(c4, c3),
        }
        for q, v in quarters.items():
            out.setdefault(q, {})[item] = v

    for item in STOCK_ITEMS:
        for q, rep in ((1, q1), (2, h1), (3, q3), (4, fy)):
            out.setdefault(q, {})[item] = rep.amount[item] if rep else None

    # 보고서 자체가 없던 분기는 제거
    present = {1: q1, 2: h1, 3: q3, 4: fy}
    return {q: vals for q, vals in out.items() if present[q] is not None}


def ttm(quarters: list[dict], item: str) -> float | None:
    """최근 4개 분기 합 (하나라도 비면 None). quarters는 시간순 정렬 가정."""
    last4 = quarters[-4:]
    if len(last4) < 4:
        return None
    vals = [q.get(item) for q in last4]
    if any(v is None for v in vals):
        return None
    return float(sum(vals))
