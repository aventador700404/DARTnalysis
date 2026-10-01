import pandas as pd
import pytest

from dartpipe.benchmark import equal_weight_index
from dartpipe.health import compute_health, percentile_ranks
from dartpipe.impact import compute_impact


def test_rights_offering_dilution():
    imp = compute_impact("rights_offering", {"nstk_ostk_cnt": "12,000,000", "bfic_tisstk_ostk": "100,000,000", "fdpp_op": "50000000000"}, None, None)
    assert imp["metrics"]["dilution_pct"] == pytest.approx(12.0)
    assert imp["notable"] is True
    assert "+12.0%" in imp["headline"]


def test_cb_uses_reported_ratio_first():
    imp = compute_impact("cb", {"cvisstk_cnt": "8000000", "cvisstk_tisstk_vs": "8.00", "bd_fta": "100000000000"}, 1e9, None)
    assert imp["metrics"]["dilution_pct"] == pytest.approx(8.0)


def test_buyback_float_and_mcap():
    imp = compute_impact("buyback", {"aqpln_stk_ostk": "1200000", "aqpln_prc_ostk": "100000000000"}, 1e8, 5e12)
    assert imp["metrics"]["float_change_pct"] == pytest.approx(-1.2)
    assert imp["metrics"]["amount_vs_mcap_pct"] == pytest.approx(2.0)
    assert "1,000억 원" in imp["headline"]


def test_unknown_subtype_returns_none():
    assert compute_impact("periodic_report", {"x": 1}, 1, 1) is None
    assert compute_impact("buyback", None, 1, 1) is None


def test_percentile_ranks_ties_and_direction():
    r = percentile_ranks({"a": 1, "b": 2, "c": 2, "d": None}, higher_is_better=True)
    assert r == {"a": 0.0, "b": 75.0, "c": 75.0}
    low = percentile_ranks({"a": 10, "b": 20}, higher_is_better=False)
    assert low == {"a": 100.0, "b": 0.0}


def test_health_sector_fallback_and_financial_exclusion():
    metrics = {f"s{i}": {"roe": 0.01 * i, "op_margin": 0.02 * i} for i in range(6)}
    metrics.update({"t1": {"roe": 0.5}, "t2": {"roe": 0.1}, "bank": {"roe": 0.2}})
    sector = {**{f"s{i}": "반도체" for i in range(6)}, "t1": "조선", "t2": "조선", "bank": "은행"}
    res = compute_health(metrics, sector, is_financial={"bank": True})
    assert res["s5"].basis["roe"] == "업종" and res["s5"].scores["profitability"] == 100.0
    assert res["t1"].basis["roe"] == "코스피 전체"  # 업종 회사 수 부족
    assert res["bank"].scores["profitability"] is None and "금융업" in res["bank"].note


def test_equal_weight_index_ignores_split_day():
    dates = pd.bdate_range("2026-01-05", periods=3)
    df = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "code": ["A"] * 3 + ["B"] * 3,
            "close": [100, 110, 121, 100, 20, 20],  # B는 둘째 날 1:5 분할
            "shares": [1, 1, 1, 1, 5, 5],
        }
    )
    idx = equal_weight_index(df)
    assert idx.iloc[0] == 100
    assert idx.iloc[1] == pytest.approx(110)  # B의 분할일 수익률(−80%)은 제외
    assert idx.iloc[2] == pytest.approx(110 * (1 + (0.10 + 0.0) / 2))
