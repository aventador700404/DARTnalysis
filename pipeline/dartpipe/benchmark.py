"""코스피 전 종목 동일가중 평균 지수.

코스피 지수는 시가총액 가중이라 삼성전자·SK하이닉스 비중이 매우 크다(2026년 6월 기준 약 56%).
그래서 '보통 종목' 대비 성과를 보려고 모든 종목의 일간 수익률을 같은 비중으로 평균 낸 지수를 따로 만든다.
"""

from __future__ import annotations

import pandas as pd

from . import config


def equal_weight_index(prices: pd.DataFrame, base: float = 100.0) -> pd.Series:
    """prices: long 형식 columns=date, code, close, shares. 반환: date → 지수 값."""
    df = prices[["date", "code", "close", "shares"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    g = df.groupby("code", sort=False)
    df["ret"] = g["close"].pct_change()
    share_jump = (g["shares"].pct_change().abs() >= config.SHARE_JUMP_EXCLUDE).fillna(False)
    df.loc[share_jump, "ret"] = pd.NA  # 분할·병합일은 가격이 불연속이라 제외
    daily = df.dropna(subset=["ret"]).groupby("date")["ret"].mean().sort_index()
    all_dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    daily = daily.reindex(all_dates).fillna(0.0)
    index = base * (1 + daily).cumprod()
    index.iloc[0] = base
    return index
