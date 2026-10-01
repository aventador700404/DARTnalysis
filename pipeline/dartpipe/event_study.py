"""공시 후 주가 변화 (명세서 4.2).

용어
- 기준일(0일째가 아니라 '1일째'): 공시 영향을 처음 받는 거래일
    · 장 마감(15:30) 전에 처음 발견한 공시 → 그날
    · 장 마감 후 발견, 또는 발견 시각을 모르는 과거 공시 → 다음 거래일 (보수적)
- 수익률(h일): 기준일 전날 종가 → 기준일부터 h번째 거래일 종가
- 초과수익률: 종목 수익률 − 벤치마크 수익률 (코스피 지수 / 코스피 동일가중 평균)

제외 규칙
- 측정 구간에 거래가 없던 날(거래정지)이 있으면 제외
- 구간 안에서 상장주식 수가 20% 이상 바뀌면 제외 (액면분할·병합 → 가격이 수정주가가 아니라서)
- 기준일 전날 시가총액이 초소형주 기준 미만이면 제외
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import config

KST = ZoneInfo("Asia/Seoul")
_CLOSE = time.fromisoformat(config.MARKET_CLOSE_HHMM)


def base_date(
    rcept_dt: date,
    first_seen_at: datetime | None,
    calendar: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    """공시의 기준일. calendar는 오름차순 거래일."""
    if first_seen_at is not None:
        seen = first_seen_at.astimezone(KST) if first_seen_at.tzinfo else first_seen_at.replace(tzinfo=KST)
        day = pd.Timestamp(seen.date())
        if day in calendar and seen.time() < _CLOSE:
            return day
        after = day
    else:
        after = pd.Timestamp(rcept_dt)
    pos = calendar.searchsorted(after, side="right")
    return calendar[pos] if pos < len(calendar) else None


@dataclass
class EventResult:
    base_date: str | None
    returns: dict[int, float | None] = field(default_factory=dict)
    excess: dict[str, dict[int, float | None]] = field(default_factory=dict)  # benchmark → horizon → 값
    excluded_reason: str | None = None


def measure_event(
    rcept_dt: date,
    first_seen_at: datetime | None,
    stock: pd.DataFrame,
    benchmarks: dict[str, pd.Series],
    calendar: pd.DatetimeIndex,
    horizons: tuple[int, ...] = config.EVENT_HORIZONS,
) -> EventResult:
    """stock: index=날짜(DatetimeIndex), columns=close, volume, shares, market_cap."""
    b = base_date(rcept_dt, first_seen_at, calendar)
    if b is None:
        return EventResult(None, excluded_reason="기준일 이후 데이터 없음")
    pos = calendar.get_loc(b)
    if pos == 0:
        return EventResult(b.date().isoformat(), excluded_reason="기준일 전날 데이터 없음")
    pre_day = calendar[pos - 1]
    result = EventResult(b.date().isoformat())

    if pre_day not in stock.index:
        result.excluded_reason = "기준일 전날 종가 없음"
        return result
    pre = stock.loc[pre_day]
    mcap = pre.get("market_cap")
    if mcap is not None and not pd.isna(mcap) and mcap < config.MICROCAP_THRESHOLD_KRW:
        result.excluded_reason = "초소형주"
        return result

    for h in horizons:
        end_pos = pos + h - 1
        if end_pos >= len(calendar):
            result.returns[h] = None
            for name in benchmarks:
                result.excess.setdefault(name, {})[h] = None
            continue
        window = calendar[pos - 1 : end_pos + 1]
        seg = stock.reindex(window)
        if seg["close"].isna().any() or (seg["volume"].fillna(0) <= 0).iloc[1:].any():
            result.excluded_reason = "측정 구간 중 거래정지"
            result.returns.clear()
            result.excess.clear()
            return result
        shares = seg["shares"].dropna()
        if len(shares) >= 2 and shares.iloc[0] > 0:
            jump = (shares / shares.iloc[0] - 1).abs().max()
            if jump >= config.SHARE_JUMP_EXCLUDE:
                result.excluded_reason = "주식 수 급변 (분할·병합 등)"
                result.returns.clear()
                result.excess.clear()
                return result
        r = float(seg["close"].iloc[-1] / seg["close"].iloc[0] - 1)
        result.returns[h] = r
        for name, series in benchmarks.items():
            bw = series.reindex([window[0], window[-1]])
            if bw.isna().any():
                result.excess.setdefault(name, {})[h] = None
            else:
                result.excess.setdefault(name, {})[h] = r - float(bw.iloc[-1] / bw.iloc[0] - 1)
    return result


def winsorized_mean(values: np.ndarray, pct: float = config.WINSOR_PCT) -> float:
    if len(values) == 0:
        return float("nan")
    lo, hi = np.quantile(values, [pct, 1 - pct])
    return float(np.clip(values, lo, hi).mean())


def summarize(values: list[float | None], min_sample: int = config.MIN_SAMPLE) -> dict:
    """유형별 통계: 표본 수, (상하위 1% 자른) 평균, 중앙값, 상승 비율, 분위수."""
    arr = np.array([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    n = int(arr.size)
    if n < min_sample:
        return {"n": n, "hidden": True, **{k: None for k in ("mean", "median", "up_ratio", "p10", "p25", "p75", "p90")}}
    p10, p25, p75, p90 = np.quantile(arr, [0.10, 0.25, 0.75, 0.90])
    return {
        "n": n,
        "hidden": False,
        "mean": winsorized_mean(arr),
        "median": float(np.median(arr)),
        "up_ratio": float((arr > 0).mean()),
        "p10": float(p10),
        "p25": float(p25),
        "p75": float(p75),
        "p90": float(p90),
    }
