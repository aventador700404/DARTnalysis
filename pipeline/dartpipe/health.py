"""종목 건강검진 (명세서 4.1).

- 항목 5개: 성장성, 수익성, 안정성, 가격, 주주환원
- 각 지표를 같은 업종 안에서 백분위(0~100)로 바꾸고, 항목 점수 = 그 항목 지표들의 평균
- 임의 기준·가중치 없음, 항목끼리 합산하지 않음
- 업종 안에 값이 있는 회사가 5개 미만이면 코스피 전체 기준
- 금융업은 v1에서 계산 제외 (재무 구조가 달라서)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import config

#: 항목 → [(지표, 높을수록 좋은가)]
AXES: dict[str, list[tuple[str, bool]]] = {
    "growth": [("revenue_cagr_3y", True), ("op_income_cagr_3y", True)],
    "profitability": [("roe", True), ("op_margin", True)],
    "stability": [("debt_ratio", False), ("interest_coverage", True)],
    "value": [("per", False), ("pbr", False), ("per_band_pct", False)],
    "shareholder_return": [("dividend_yield", True), ("buyback_yield", True)],
}
AXIS_LABELS = {
    "growth": "성장성",
    "profitability": "수익성",
    "stability": "안정성",
    "value": "가격",
    "shareholder_return": "주주환원",
}


def _valid(v: object) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def percentile_ranks(values: dict[str, float | None], higher_is_better: bool) -> dict[str, float]:
    """평균 순위 방식 백분위. 값이 없는 종목은 결과에서 빠짐."""
    items = [(k, float(v)) for k, v in values.items() if _valid(v)]
    n = len(items)
    if n == 0:
        return {}
    if n == 1:
        return {items[0][0]: 50.0}
    ordered = sorted(items, key=lambda kv: kv[1])
    ranks: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg_rank = (i + j) / 2
        for k in range(i, j + 1):
            ranks[ordered[k][0]] = avg_rank
        i = j + 1
    out = {code: r / (n - 1) * 100 for code, r in ranks.items()}
    if not higher_is_better:
        out = {code: 100 - s for code, s in out.items()}
    return out


@dataclass
class HealthResult:
    scores: dict[str, float | None]  # 항목 → 점수
    metric_scores: dict[str, float | None]  # 지표 → 백분위
    basis: dict[str, str]  # 지표 → "업종" | "코스피 전체"
    note: str | None = None


def compute_health(
    metrics: dict[str, dict[str, float | None]],
    sector_of: dict[str, str | None],
    is_financial: dict[str, bool] | None = None,
    audit_ok: dict[str, bool] | None = None,
) -> dict[str, HealthResult]:
    """metrics: 종목코드 → {지표: 값}. sector_of: 종목코드 → 업종(테마) 키."""
    is_financial = is_financial or {}
    audit_ok = audit_ok or {}
    codes = [c for c in metrics if not is_financial.get(c)]

    metric_names = {m for axis in AXES.values() for m, _ in axis}
    metric_scores: dict[str, dict[str, float]] = {c: {} for c in codes}
    basis: dict[str, dict[str, str]] = {c: {} for c in codes}

    for metric in metric_names:
        higher = next(h for axis in AXES.values() for m, h in axis if m == metric)
        market_vals = {c: metrics[c].get(metric) for c in codes}
        market_scores = percentile_ranks(market_vals, higher)
        sectors: dict[str, list[str]] = {}
        for c in codes:
            sectors.setdefault(sector_of.get(c) or "_none", []).append(c)
        for sector, members in sectors.items():
            vals = {c: market_vals[c] for c in members}
            n_valid = sum(_valid(v) for v in vals.values())
            if sector != "_none" and n_valid >= config.MIN_PEERS_FOR_SECTOR_PERCENTILE:
                scores = percentile_ranks(vals, higher)
                label = "업종"
            else:
                scores = {c: market_scores[c] for c in members if c in market_scores}
                label = "코스피 전체"
            for c, s in scores.items():
                metric_scores[c][metric] = s
                basis[c][metric] = label

    out: dict[str, HealthResult] = {}
    for c in codes:
        axis_scores: dict[str, float | None] = {}
        for axis, ms in AXES.items():
            vals = [metric_scores[c][m] for m, _ in ms if m in metric_scores[c]]
            axis_scores[axis] = round(sum(vals) / len(vals), 1) if vals else None
        note = None
        if audit_ok.get(c) is False:
            axis_scores["stability"] = 0.0
            note = "최근 감사의견이 '적정'이 아니어서 안정성 0점"
        out[c] = HealthResult(
            scores=axis_scores,
            metric_scores={m: round(v, 1) for m, v in metric_scores[c].items()},
            basis=basis[c],
            note=note,
        )
    for c in metrics:
        if is_financial.get(c):
            out[c] = HealthResult({a: None for a in AXES}, {}, {}, note="금융업은 재무 구조가 달라 v1에서 계산하지 않음")
    return out


def cagr(now: float | None, before: float | None, years: float) -> float | None:
    if not (_valid(now) and _valid(before)) or before <= 0 or now <= 0:
        return None
    return (now / before) ** (1 / years) - 1
