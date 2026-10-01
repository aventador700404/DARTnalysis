"""밸류에이션 지표 (명세서 4.4).

미래 정보를 쓰지 않도록(look-ahead 방지) 재무 값은 보고서가 공시된 날(available_from)부터만 사용한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_ttm(quarters: pd.DataFrame) -> pd.DataFrame:
    """quarters: 시간순 정렬, columns=revenue, operating_income, net_income_parent, interest_expense,
    operating_cash_flow, equity_parent, total_liabilities, total_equity, available_from ..."""
    q = quarters.copy()
    for col in ("revenue", "operating_income", "net_income_parent", "net_income", "interest_expense", "operating_cash_flow"):
        if col in q:
            q[f"ttm_{col}"] = q[col].rolling(4, min_periods=4).sum()
    if "equity_parent" in q:
        q["avg_equity_parent"] = (q["equity_parent"] + q["equity_parent"].shift(4)) / 2
        q["roe"] = q["ttm_net_income_parent"] / q["avg_equity_parent"]
    if {"ttm_operating_income", "ttm_revenue"} <= set(q.columns):
        q["op_margin"] = q["ttm_operating_income"] / q["ttm_revenue"]
    if {"total_liabilities", "total_equity"} <= set(q.columns):
        q["debt_ratio"] = q["total_liabilities"] / q["total_equity"]
    return q


def daily_multiples(prices: pd.DataFrame, quarters: pd.DataFrame) -> pd.DataFrame:
    """prices: columns=date, market_cap (한 종목). quarters: add_ttm 결과 + available_from.

    반환: date, market_cap, per, pbr (적자면 PER = NaN)."""
    p = prices[["date", "market_cap"]].copy()
    p["date"] = pd.to_datetime(p["date"])
    q = quarters.dropna(subset=["available_from"]).copy()
    q["available_from"] = pd.to_datetime(q["available_from"])
    q = q.sort_values("available_from")[["available_from", "ttm_net_income_parent", "equity_parent"]]
    merged = pd.merge_asof(p.sort_values("date"), q, left_on="date", right_on="available_from", direction="backward")
    ni = merged["ttm_net_income_parent"]
    merged["per"] = np.where(ni > 0, merged["market_cap"] / ni, np.nan)
    eq = merged["equity_parent"]
    merged["pbr"] = np.where(eq > 0, merged["market_cap"] / eq, np.nan)
    return merged[["date", "market_cap", "per", "pbr"]]


def band_position(series: pd.Series, current: float | None, years: int = 5) -> float | None:
    """현재 값이 과거 N년 분포에서 몇 번째 백분위인지 (0=가장 쌌을 때, 100=가장 비쌌을 때)."""
    if current is None or not np.isfinite(current):
        return None
    s = series.dropna()
    if s.empty:
        return None
    if isinstance(s.index, pd.DatetimeIndex):
        s = s[s.index >= s.index.max() - pd.DateOffset(years=years)]
    s = s[s > 0]
    if len(s) < 20:
        return None
    return float((s < current).mean() * 100)
