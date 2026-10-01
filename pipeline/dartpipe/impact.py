"""공시 → 재무 영향 (명세서 4.3).

입력은 OpenDART 주요사항보고서·지분공시 API 응답 1건(dict, 필드명 그대로).
출력은 화면 공시 패널에 그대로 쓰는 dict:
    {"kind": ..., "headline": "주식 수 +12.0% (희석)", "metrics": {...}, "notable": bool}
"""

from __future__ import annotations

from . import config
from .financials import parse_amount


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b * 100


def _fmt_pct(v: float, signed: bool = True) -> str:
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def _fmt_krw(v: float) -> str:
    """원 → '1,234억 원' / '1.2조 원'."""
    eok = v / 1e8
    if abs(eok) >= 10_000:
        return f"{eok / 10_000:,.1f}조 원"
    return f"{eok:,.0f}억 원"


def rights_offering(d: dict, shares_outstanding: float | None = None) -> dict:
    new = parse_amount(d.get("nstk_ostk_cnt"))
    before = parse_amount(d.get("bfic_tisstk_ostk")) or shares_outstanding
    dilution = _pct(new, before)
    purposes = {
        "시설자금": d.get("fdpp_fclt"),
        "운영자금": d.get("fdpp_op"),
        "채무상환": d.get("fdpp_dtrp"),
        "타법인 증권 취득": d.get("fdpp_ocsa"),
        "영업양수": d.get("fdpp_bsninh"),
        "기타": d.get("fdpp_etc"),
    }
    purposes = {k: parse_amount(v) for k, v in purposes.items() if parse_amount(v)}
    total = sum(purposes.values()) if purposes else None
    return {
        "kind": "rights_offering",
        "headline": f"주식 수 {_fmt_pct(dilution)} → 주당 가치 희석" if dilution is not None else "유상증자",
        "metrics": {
            "new_shares": new,
            "shares_before": before,
            "dilution_pct": dilution,
            "raise_amount": total,
            "main_purpose": max(purposes, key=purposes.get) if purposes else None,
            "method": d.get("ic_mthn"),
        },
        "notable": dilution is not None and dilution >= config.NOTABLE_DILUTION_PCT,
    }


def convertible(d: dict, shares_outstanding: float | None = None, kind: str = "cb") -> dict:
    """전환사채(cb)·신주인수권부사채(bw). 전부 주식이 되면 늘어날 주식 수 = 잠재 희석."""
    if kind == "bw":
        conv = parse_amount(d.get("nstk_isstk_cnt"))
        ratio = parse_amount(d.get("nstk_isstk_tisstk_vs"))
        price = parse_amount(d.get("ex_prc"))
    else:
        conv = parse_amount(d.get("cvisstk_cnt"))
        ratio = parse_amount(d.get("cvisstk_tisstk_vs"))
        price = parse_amount(d.get("cv_prc"))
    dilution = ratio if ratio is not None else _pct(conv, shares_outstanding)
    face = parse_amount(d.get("bd_fta"))
    label = "전부 전환 시" if kind == "cb" else "전부 행사 시"
    return {
        "kind": kind,
        "headline": f"{label} 주식 수 {_fmt_pct(dilution)} (잠재 희석)" if dilution is not None else "메자닌 발행",
        "metrics": {
            "face_amount": face,
            "conversion_price": price,
            "potential_shares": conv,
            "dilution_pct": dilution,
        },
        "notable": dilution is not None and dilution >= config.NOTABLE_DILUTION_PCT,
    }


def buyback(d: dict, shares_outstanding: float | None, market_cap: float | None) -> dict:
    qty = parse_amount(d.get("aqpln_stk_ostk"))
    amount = parse_amount(d.get("aqpln_prc_ostk"))
    float_change = _pct(qty, shares_outstanding)
    mcap_pct = _pct(amount, market_cap)
    parts = []
    if float_change is not None:
        parts.append(f"유통주식 {_fmt_pct(-float_change)}")
    if amount:
        parts.append(f"약 {_fmt_krw(amount)} 환원")
    return {
        "kind": "buyback",
        "headline": ", ".join(parts) or "자기주식 취득",
        "metrics": {
            "planned_shares": qty,
            "planned_amount": amount,
            "float_change_pct": -float_change if float_change is not None else None,
            "amount_vs_mcap_pct": mcap_pct,
            "method": d.get("aq_mth"),
            "period": [d.get("aqexpd_bgd"), d.get("aqexpd_edd")],
        },
        "notable": mcap_pct is not None and mcap_pct >= config.NOTABLE_BUYBACK_MCAP_PCT,
    }


def treasury_disposal(d: dict, shares_outstanding: float | None) -> dict:
    qty = parse_amount(d.get("dppln_stk_ostk"))
    amount = parse_amount(d.get("dppln_prc_ostk"))
    float_change = _pct(qty, shares_outstanding)
    return {
        "kind": "treasury_disposal",
        "headline": f"유통주식 {_fmt_pct(float_change)}" if float_change is not None else "자기주식 처분",
        "metrics": {"planned_shares": qty, "planned_amount": amount, "float_change_pct": float_change},
        "notable": False,
    }


def ownership_change(d: dict, source: str) -> dict:
    """source: 'major_holder'(대량보유, majorstock) 또는 'insider'(임원·주요주주, elestock)."""
    if source == "major_holder":
        rate_change = parse_amount(d.get("stkrt_irds"))
        rate = parse_amount(d.get("stkrt"))
        who = d.get("repror")
    else:
        rate_change = parse_amount(d.get("sp_stock_lmp_irds_rate"))
        rate = parse_amount(d.get("sp_stock_lmp_rate"))
        who = d.get("repror")
    headline = f"{who or '보고자'} 지분 {rate_change:+.2f}%p" if rate_change is not None else "지분 변동"
    return {
        "kind": source,
        "headline": headline,
        "metrics": {"holder": who, "stake_pct": rate, "stake_change_pp": rate_change},
        "notable": rate_change is not None and abs(rate_change) >= config.NOTABLE_OWNERSHIP_PP,
    }


def compute_impact(subtype: str | None, detail: dict | None, shares_outstanding: float | None, market_cap: float | None) -> dict | None:
    if not detail or not subtype:
        return None
    if subtype == "rights_offering":
        return rights_offering(detail, shares_outstanding)
    if subtype in ("cb", "bw"):
        return convertible(detail, shares_outstanding, kind=subtype)
    if subtype == "buyback":
        return buyback(detail, shares_outstanding, market_cap)
    if subtype == "treasury_disposal":
        return treasury_disposal(detail, shares_outstanding)
    if subtype in ("major_holder", "insider"):
        return ownership_change(detail, subtype)
    return None
