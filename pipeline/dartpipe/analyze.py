"""원천 데이터 → 화면/DB에 쓰는 결과 테이블.

실제 파이프라인(jobs/)과 가상 데이터 생성기(mock/)가 같은 함수를 쓴다.
그래서 웹에서 보이는 숫자는 실제 데이터를 넣었을 때와 똑같은 로직으로 계산된 값이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from . import config
from .benchmark import equal_weight_index
from .classify import CATEGORIES, classify
from .event_study import measure_event, summarize
from .health import AXES, cagr, compute_health
from .impact import compute_impact
from .valuation import add_ttm, band_position, daily_multiples

SUBTYPE_LABELS = {
    "rights_offering": "유상증자",
    "bonus_issue": "무상증자",
    "capital_reduction": "감자",
    "cb": "전환사채 발행",
    "bw": "신주인수권부사채 발행",
    "eb": "교환사채 발행",
    "buyback": "자사주 취득",
    "buyback_trust": "자사주 신탁계약",
    "treasury_disposal": "자사주 처분",
    "cancellation": "자사주 소각",
    "major_holder": "5% 대량보유 보고",
    "insider": "임원·주요주주 지분 보고",
    "largest_holder_change": "최대주주 변경",
    "periodic_report": "정기보고서",
    "preliminary_earnings": "잠정실적",
    "earnings_change": "손익구조 30% 이상 변동",
}

BENCHMARKS = ("kospi", "ew")


@dataclass
class Universe:
    companies: list[dict]  # code, corp_code, name, ksic, ksic_name, themes, is_financial
    prices: pd.DataFrame  # long: date, code, open, high, low, close, volume, market_cap, shares
    kospi: pd.Series  # date → 코스피 지수
    quarters: dict[str, pd.DataFrame]  # code → 분기 재무 (financials.quarterize_year 결과를 쌓은 것)
    disclosures: list[dict]  # rcept_no, code, report_nm, rcept_dt, first_seen_at, detail
    dividends: dict[str, float] = field(default_factory=dict)  # code → 최근 연간 배당 총액(원)
    audit_ok: dict[str, bool] = field(default_factory=dict)
    as_of: date | None = None


@dataclass
class Outputs:
    index_daily: list[dict]
    disclosures: list[dict]
    impacts: list[dict]
    stats: list[dict]
    scores: list[dict]
    valuation: list[dict]
    valuation_history: list[dict]
    financials: list[dict]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return v.isoformat()[:10]
    return v


def _clean_dict(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _clean_dict(v)
        elif isinstance(v, list):
            out[k] = [_clean(x) for x in v]
        else:
            out[k] = _clean(v)
    return out


def build(u: Universe) -> Outputs:
    prices = u.prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    calendar = pd.DatetimeIndex(sorted(prices["date"].unique()))
    kospi = u.kospi.copy()
    kospi.index = pd.to_datetime(kospi.index)
    ew = equal_weight_index(prices)
    benches = {"kospi": kospi, "ew": ew}
    as_of = pd.Timestamp(u.as_of) if u.as_of else calendar[-1]

    by_code = {code: df.set_index("date").sort_index() for code, df in prices.groupby("code")}

    index_daily = [
        {"date": d.date().isoformat(), "kospi": _clean(kospi.get(d)), "kospi_ew": _clean(ew.get(d))}
        for d in calendar
    ]

    # ── 공시: 분류 → 기준일·수익률 → 재무 영향 ──────────────────────
    disc_rows, impact_rows = [], []
    for d in sorted(u.disclosures, key=lambda x: (x["rcept_dt"], x["rcept_no"])):
        cls = classify(d["report_nm"])
        rcept_dt = d["rcept_dt"] if isinstance(d["rcept_dt"], date) else date.fromisoformat(str(d["rcept_dt"])[:10])
        seen = d.get("first_seen_at")
        if isinstance(seen, str):
            seen = datetime.fromisoformat(seen)
        stock = by_code.get(d["code"])
        group_key = cls.subtype or cls.category
        disc_rows.append(
            {
                "rcept_no": d["rcept_no"],
                "code": d["code"],
                "report_nm": d["report_nm"],
                "rcept_dt": rcept_dt.isoformat(),
                "first_seen_at": seen.isoformat() if seen else None,
                "category": cls.category,
                "subtype": cls.subtype,
                "group_key": group_key,
                "is_correction": cls.is_correction,
            }
        )
        if stock is None:
            continue
        ev = measure_event(rcept_dt, seen, stock, benches, calendar)
        shares = mcap = None
        if ev.base_date:
            pos = calendar.get_loc(pd.Timestamp(ev.base_date))
            pre_day = calendar[pos - 1] if pos > 0 else None
            if pre_day is not None and pre_day in stock.index:
                shares = _clean(stock.loc[pre_day, "shares"])
                mcap = _clean(stock.loc[pre_day, "market_cap"])
        impact = None if cls.is_correction else compute_impact(cls.subtype, d.get("detail"), shares, mcap)
        row = {
            "rcept_no": d["rcept_no"],
            "code": d["code"],
            "group_key": group_key,
            "base_date": ev.base_date,
            "excluded_reason": ev.excluded_reason,
            "impact": impact,
            "notable": bool(impact and impact.get("notable")),
        }
        for h in config.EVENT_HORIZONS:
            row[f"ret_{h}"] = _clean(ev.returns.get(h))
            for b in BENCHMARKS:
                row[f"ex_{b}_{h}"] = _clean(ev.excess.get(b, {}).get(h))
        impact_rows.append(_clean_dict(row))

    # ── 유형별 통계 (정정공시 제외) ─────────────────────────
    corrections = {r["rcept_no"] for r in disc_rows if r["is_correction"]}
    stats_rows = []
    keys = sorted({r["group_key"] for r in impact_rows})
    for key in keys:
        rows = [r for r in impact_rows if r["group_key"] == key and r["rcept_no"] not in corrections and not r["excluded_reason"]]
        category = next(dr["category"] for dr in disc_rows if dr["group_key"] == key)
        for h in config.EVENT_HORIZONS:
            for b in BENCHMARKS:
                s = summarize([r.get(f"ex_{b}_{h}") for r in rows])
                stats_rows.append(
                    _clean_dict(
                        {
                            "group_key": key,
                            "group_label": SUBTYPE_LABELS.get(key, CATEGORIES.get(key, key)),
                            "category": category,
                            "horizon": h,
                            "benchmark": b,
                            **s,
                        }
                    )
                )

    # ── 재무·밸류에이션·건강검진 ────────────────────────────
    fin_rows, val_rows, val_hist = [], [], []
    metrics: dict[str, dict[str, float | None]] = {}
    company_by_code = {c["code"]: c for c in u.companies}
    buyback_amounts: dict[str, float] = {}
    one_year_ago = (as_of - pd.DateOffset(years=1)).date().isoformat()
    for r in impact_rows:
        imp = r.get("impact") or {}
        if imp.get("kind") == "buyback" and r.get("base_date") and r["base_date"] >= one_year_ago:
            amt = (imp.get("metrics") or {}).get("planned_amount") or 0
            buyback_amounts[r["code"]] = buyback_amounts.get(r["code"], 0) + amt

    for code, comp in company_by_code.items():
        q = u.quarters.get(code)
        stock = by_code.get(code)
        if q is None or q.empty or stock is None:
            continue
        q = add_ttm(q.sort_values(["year", "quarter"]).reset_index(drop=True))
        for rec in q.to_dict("records"):
            fin_rows.append(_clean_dict({"code": code, **rec}))

        mult = daily_multiples(stock.reset_index()[["date", "market_cap"]], q).set_index("date")
        mult = mult[mult.index <= as_of]
        last = mult.iloc[-1]
        q_avail = q[pd.to_datetime(q["available_from"]) <= as_of]
        lq = q_avail.iloc[-1] if not q_avail.empty else None
        q12 = q_avail.iloc[-13] if len(q_avail) >= 13 else None
        mcap = float(last["market_cap"])
        ttm_interest = lq.get("ttm_interest_expense") if lq is not None else None
        m = {
            "per": _clean(last["per"]),
            "pbr": _clean(last["pbr"]),
            "per_band_pct": band_position(mult["per"], _clean(last["per"])),
            "pbr_band_pct": band_position(mult["pbr"], _clean(last["pbr"])),
            "roe": _clean(lq["roe"]) if lq is not None else None,
            "op_margin": _clean(lq["op_margin"]) if lq is not None else None,
            "debt_ratio": _clean(lq["debt_ratio"]) if lq is not None else None,
            "interest_coverage": _clean(lq["ttm_operating_income"] / ttm_interest)
            if lq is not None and ttm_interest and ttm_interest > 0
            else None,
            "revenue_cagr_3y": cagr(_clean(lq["ttm_revenue"]), _clean(q12["ttm_revenue"]), 3)
            if lq is not None and q12 is not None
            else None,
            "op_income_cagr_3y": cagr(_clean(lq["ttm_operating_income"]), _clean(q12["ttm_operating_income"]), 3)
            if lq is not None and q12 is not None
            else None,
            "dividend_yield": (u.dividends.get(code) or 0) / mcap if mcap else None,
            "buyback_yield": buyback_amounts.get(code, 0) / mcap if mcap else None,
            "market_cap": mcap,
            "ttm_revenue": _clean(lq["ttm_revenue"]) if lq is not None else None,
            "ttm_operating_income": _clean(lq["ttm_operating_income"]) if lq is not None else None,
        }
        metrics[code] = m
        val_rows.append(_clean_dict({"code": code, "as_of": as_of.date().isoformat(), **m}))
        monthly = mult.resample("ME").last().dropna(how="all")
        for d, row in monthly.iterrows():
            val_hist.append(_clean_dict({"code": code, "date": d.date().isoformat(), "per": row["per"], "pbr": row["pbr"]}))

    sector_of = {c["code"]: (c.get("themes") or [None])[0] or c.get("ksic") for c in u.companies}
    health = compute_health(
        metrics,
        sector_of,
        is_financial={c["code"]: bool(c.get("is_financial")) for c in u.companies},
        audit_ok=u.audit_ok,
    )
    score_rows = [
        _clean_dict(
            {
                "code": code,
                "as_of": as_of.date().isoformat(),
                **{axis: res.scores.get(axis) for axis in AXES},
                "metric_scores": res.metric_scores,
                "basis": res.basis,
                "note": res.note,
            }
        )
        for code, res in health.items()
    ]

    return Outputs(
        index_daily=index_daily,
        disclosures=disc_rows,
        impacts=impact_rows,
        stats=stats_rows,
        scores=score_rows,
        valuation=val_rows,
        valuation_history=val_hist,
        financials=fin_rows,
    )
