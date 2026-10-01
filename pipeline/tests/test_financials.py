import pytest

from dartpipe.clients.dart import REPRT_ANNUAL, REPRT_H1, REPRT_Q1, REPRT_Q3
from dartpipe.financials import extract_report, parse_amount, quarterize_year, ttm


def row(sj, aid, nm, th, add=""):
    return {"sj_div": sj, "account_id": aid, "account_nm": nm, "thstrm_amount": th, "thstrm_add_amount": add}


# 분기 실제 매출 100, 110, 120, 130 / 현금흐름 10, 20, 30, 40
REPORTS = {
    REPRT_Q1: [row("IS", "ifrs-full_Revenue", "매출액", "100", "100"), row("CF", "x", "영업활동현금흐름", "10"), row("BS", "ifrs-full_Equity", "자본총계", "1,000")],
    REPRT_H1: [row("IS", "ifrs-full_Revenue", "매출액", "110", "210"), row("CF", "x", "영업활동현금흐름", "30"), row("BS", "ifrs-full_Equity", "자본총계", "1,050")],
    REPRT_Q3: [row("IS", "ifrs-full_Revenue", "매출액", "120", "330"), row("CF", "x", "영업활동현금흐름", "60"), row("BS", "ifrs-full_Equity", "자본총계", "1,100")],
    REPRT_ANNUAL: [row("IS", "ifrs-full_Revenue", "매출액", "460"), row("CF", "x", "영업활동현금흐름", "100"), row("BS", "ifrs-full_Equity", "자본총계", "1,200")],
}


def test_parse_amount():
    assert parse_amount("1,234") == 1234
    assert parse_amount("-500") == -500
    assert parse_amount("") is None and parse_amount("-") is None and parse_amount(None) is None


def test_quarterize_income_cashflow_balance():
    q = quarterize_year({k: extract_report(v) for k, v in REPORTS.items()})
    assert [q[i]["revenue"] for i in (1, 2, 3, 4)] == [100, 110, 120, 130]  # 4분기 = 연간 − 3분기 누적
    assert [q[i]["operating_cash_flow"] for i in (1, 2, 3, 4)] == [10, 20, 30, 40]  # CF는 누적 차분
    assert [q[i]["total_equity"] for i in (1, 2, 3, 4)] == [1000, 1050, 1100, 1200]  # BS는 시점 값


def test_name_fallback_when_custom_account_id():
    rep = extract_report([row("IS", "entity00123_CustomRevenue", "영업수익", "777", "777")])
    assert rep.amount["revenue"] == 777


def test_missing_q3_makes_q4_unknown():
    reports = {k: extract_report(v) for k, v in REPORTS.items() if k != REPRT_Q3}
    q = quarterize_year(reports)
    assert 3 not in q
    assert q[4]["revenue"] is None


def test_ttm():
    quarters = [{"revenue": v} for v in (1, 2, 3, 4, 5)]
    assert ttm(quarters, "revenue") == pytest.approx(14)
    assert ttm(quarters[:3], "revenue") is None
