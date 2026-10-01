from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from dartpipe.event_study import base_date, measure_event, summarize

KST = ZoneInfo("Asia/Seoul")
CAL = pd.bdate_range("2026-03-02", periods=40)


def stock_frame(close=None, volume=None, shares=None):
    n = len(CAL)
    close = np.full(n, 100.0) if close is None else close
    return pd.DataFrame(
        {
            "close": close,
            "volume": np.full(n, 1000.0) if volume is None else volume,
            "shares": np.full(n, 1e8) if shares is None else shares,
            "market_cap": close * 1e8 * 100,
        },
        index=CAL,
    )


def test_base_date_rules():
    tue = date(2026, 3, 3)
    # 장중 발견 → 당일
    assert base_date(tue, datetime(2026, 3, 3, 10, 0, tzinfo=KST), CAL) == pd.Timestamp("2026-03-03")
    # 장 마감 후 발견 → 다음 거래일
    assert base_date(tue, datetime(2026, 3, 3, 17, 0, tzinfo=KST), CAL) == pd.Timestamp("2026-03-04")
    # 시각 모름 → 다음 거래일 (보수적)
    assert base_date(tue, None, CAL) == pd.Timestamp("2026-03-04")
    # 금요일 저녁 → 월요일
    assert base_date(date(2026, 3, 6), datetime(2026, 3, 6, 18, 0, tzinfo=KST), CAL) == pd.Timestamp("2026-03-09")


def test_excess_return_against_benchmark():
    close = np.full(len(CAL), 100.0)
    close[5:] = 110.0  # 기준일(5번째)부터 +10%
    bench = pd.Series(np.full(len(CAL), 1000.0), index=CAL)
    bench.iloc[5:] = 1020.0  # 시장 +2%
    res = measure_event(CAL[4].date(), None, stock_frame(close), {"kospi": bench}, CAL, horizons=(5,))
    assert res.base_date == CAL[5].date().isoformat()
    assert res.returns[5] == pytest.approx(0.10)
    assert res.excess["kospi"][5] == pytest.approx(0.08)


def test_excluded_on_trading_halt_and_share_jump():
    vol = np.full(len(CAL), 1000.0)
    vol[7] = 0
    res = measure_event(CAL[4].date(), None, stock_frame(volume=vol), {}, CAL, horizons=(5,))
    assert res.excluded_reason == "측정 구간 중 거래정지"

    shares = np.full(len(CAL), 1e8)
    shares[8:] = 5e8  # 1:5 액면분할
    res = measure_event(CAL[4].date(), None, stock_frame(shares=shares), {}, CAL, horizons=(5,))
    assert res.excluded_reason and "분할" in res.excluded_reason


def test_window_beyond_data_is_none():
    res = measure_event(CAL[-3].date(), None, stock_frame(), {}, CAL, horizons=(5,))
    assert res.returns[5] is None and res.excluded_reason is None


def test_summarize_hides_small_samples_and_winsorizes():
    assert summarize([0.1, 0.2])["hidden"] is True
    vals = [0.01] * 99 + [5.0]  # 극단값 하나
    s = summarize(vals)
    assert s["n"] == 100 and s["median"] == pytest.approx(0.01)
    assert s["mean"] < 0.06  # 그냥 평균(0.0599)보다 극단값 영향이 작음
    assert s["up_ratio"] == 1.0
