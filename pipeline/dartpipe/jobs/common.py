"""백필·일일 배치가 같이 쓰는 단계들.

각 함수는 외부 클라이언트와 저장소(store)를 인자로 받는다 → 테스트에서 가짜로 바꿔 끼울 수 있음.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from .. import ksic
from ..analyze import Outputs, Universe, build
from ..classify import classify
from ..clients.dart import REPORT_CODES, DartClient
from ..clients.datagokr import DataGoKrClient, to_price_row
from ..clients.naver import NaverClient
from ..financials import extract_report, parse_amount, quarterize_year

log = logging.getLogger("dartpipe")
KST = ZoneInfo("Asia/Seoul")

#: 상세 API를 불러 재무 영향을 계산할 공시 세부 유형
DETAIL_SUBTYPES = ("rights_offering", "cb", "bw", "buyback", "treasury_disposal")
#: 뉴스를 붙일 공시 유형
NEWS_CATEGORIES = ("financing", "buyback", "ownership")
#: 분기 → 해당 분기 실적이 담긴 보고서 코드
QUARTER_REPORT = dict(zip((1, 2, 3, 4), REPORT_CODES))


def today_kst() -> date:
    return datetime.now(KST).date()


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


# ── 1. 종목 목록 ─────────────────────────────────────────────
def refresh_companies(dart: DartClient, gokr: DataGoKrClient, store, as_of: date, limit: int | None = None) -> list[dict]:
    """코스피 보통주 목록 = 금융위 시세(KOSPI) ∩ DART 고유번호(stock_code가 있는 회사)."""
    listed: dict[str, str] = {}
    for back in range(0, 10):  # 최근 거래일 찾기
        d = as_of - timedelta(days=back)
        for item in gokr.stock_prices(bas_dt=ymd(d), market="KOSPI"):
            listed[item["srtnCd"].lstrip("A")] = item.get("itmsNm", "")
        if listed:
            break
    corp_by_stock = {c["stock_code"]: c for c in dart.corp_codes() if c.get("stock_code")}
    codes = sorted(c for c in listed if c in corp_by_stock)
    if limit:
        codes = codes[:limit]
    rows = []
    for code in codes:
        corp = corp_by_stock[code]
        info = dart.company(corp["corp_code"])
        induty = info.get("induty_code")
        rows.append(
            {
                "code": code,
                "corp_code": corp["corp_code"],
                "name": info.get("stock_name") or corp["corp_name"],
                "market": "KOSPI",
                "ksic": ksic.ksic_group(induty),
                "ksic_name": ksic.ksic_name(induty),
                "is_financial": ksic.is_financial(induty),
            }
        )
    store.upsert("companies", rows, update_columns=["corp_code", "name", "market", "ksic", "ksic_name", "is_financial"])
    log.info("companies: %d", len(rows))
    return rows


# ── 2. 주가·지수 ─────────────────────────────────────────────
def load_prices(gokr: DataGoKrClient, store, begin: date, end: date, codes: set[str]) -> int:
    """begin 이상 end 미만 기간의 코스피 일별 시세."""
    rows = []
    for item in gokr.stock_prices(begin_bas_dt=ymd(begin), end_bas_dt=ymd(end), market="KOSPI"):
        r = to_price_row(item)
        if r["code"] in codes:
            r.pop("name", None)
            rows.append(r)
    n = store.upsert("prices_daily", rows)
    log.info("prices_daily: %d rows (%s ~ %s)", n, begin, end)
    return n


def load_index(gokr: DataGoKrClient, store, begin: date, end: date) -> int:
    rows = []
    for item in gokr.index_prices("코스피", begin_bas_dt=ymd(begin), end_bas_dt=ymd(end)):
        d = item["basDt"]
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "kospi": float(item["clpr"])})
    return store.upsert("index_daily", rows, update_columns=["kospi"])


# ── 3. 공시 ───────────────────────────────────────────────────
def load_disclosures(dart: DartClient, store, begin: date, end: date, codes: set[str]) -> list[dict]:
    """코스피 공시 목록. 회사 미지정 검색은 3개월 제한이라 90일씩 나눠 조회.
    이미 있는 공시는 건드리지 않음 (실시간 수집이 기록한 '처음 발견 시각' 보존)."""
    rows = []
    start = begin
    while start <= end:
        stop = min(start + timedelta(days=89), end)
        for it in dart.iter_disclosures(ymd(start), ymd(stop), corp_cls="Y"):
            code = (it.get("stock_code") or "").strip()
            if code not in codes:
                continue
            cls = classify(it["report_nm"])
            rows.append(
                {
                    "rcept_no": it["rcept_no"],
                    "code": code,
                    "corp_code": it["corp_code"],
                    "report_nm": it["report_nm"].strip(),
                    "rcept_dt": f"{it['rcept_dt'][:4]}-{it['rcept_dt'][4:6]}-{it['rcept_dt'][6:]}",
                    "category": cls.category,
                    "subtype": cls.subtype,
                    "group_key": cls.subtype or cls.category,
                    "is_correction": cls.is_correction,
                }
            )
        start = stop + timedelta(days=1)
    store.upsert("disclosures", rows)
    log.info("disclosures: %d", len(rows))
    return rows


def attach_details(dart: DartClient, store, disclosures: list[dict]) -> int:
    """재무 영향 계산용 상세(주요사항보고서·지분공시)를 붙인다. 회사·유형별로 한 번에 조회."""
    need = [d for d in disclosures if not d.get("detail") and (d.get("subtype") in DETAIL_SUBTYPES or d.get("subtype") in ("major_holder", "insider"))]
    by_key: dict[tuple[str, str], list[dict]] = {}
    for d in need:
        by_key.setdefault((d["corp_code"], d["subtype"]), []).append(d)
    updated = []
    for (corp_code, subtype), items in by_key.items():
        if subtype == "major_holder":
            found = dart.major_holders(corp_code)
        elif subtype == "insider":
            found = dart.insider_holdings(corp_code)
        else:
            dates = sorted(str(i["rcept_dt"]).replace("-", "") for i in items)
            found = dart.major_report(subtype, corp_code, dates[0], dates[-1])
        by_no = {f["rcept_no"]: f for f in found}
        for i in items:
            if i["rcept_no"] in by_no:
                updated.append({"rcept_no": i["rcept_no"], "detail": by_no[i["rcept_no"]]})
    if updated:
        store.set_details(updated)
    log.info("details attached: %d", len(updated))
    return len(updated)


# ── 4. 재무 ───────────────────────────────────────────────────
def load_financials(dart: DartClient, store, corp_code: str, code: str, years: list[int]) -> int:
    """연도별 4개 보고서 → 분기 값. 보고서 접수일을 '이 숫자를 쓸 수 있게 된 날'로 기록."""
    rows = []
    for year in years:
        reports, fs_divs, rcept = {}, {}, {}
        for rc in REPORT_CODES:
            fs_div, raw = dart.financial_statements_any(corp_code, year, rc)
            if raw:
                reports[rc] = extract_report(raw)
                fs_divs[rc] = fs_div
                no = raw[0].get("rcept_no", "")
                rcept[rc] = f"{no[:4]}-{no[4:6]}-{no[6:8]}" if len(no) >= 8 else None
        for q, vals in quarterize_year(reports).items():
            rc = QUARTER_REPORT[q]
            rows.append(
                {
                    "code": code,
                    "year": year,
                    "quarter": q,
                    "period_end": f"{year}-{q * 3:02d}-{30 if q in (2, 3) else 31}",
                    "available_from": rcept.get(rc),
                    "fs_div": fs_divs.get(rc),
                    **vals,
                }
            )
    return store.upsert("financials", rows)


def load_annual_facts(dart: DartClient, store, corp_code: str, code: str, year: int) -> None:
    div_total = None
    for r in dart.dividends(corp_code, year):
        if "현금배당금총액" in (r.get("se") or ""):
            v = parse_amount(r.get("thstrm"))
            div_total = v * 1_000_000 if v is not None else None  # 단위: 백만원
            break
    opinion = None
    for r in dart.audit_opinion(corp_code, year):
        if r.get("adt_opinion"):
            opinion = r["adt_opinion"]
            break
    store.upsert("annual_facts", [{"code": code, "year": year, "dividend_total": div_total, "audit_opinion": opinion}])


# ── 5. 뉴스 ───────────────────────────────────────────────────
def attach_news(naver: NaverClient, store, disclosures: list[dict], names: dict[str, str], limit: int = 30) -> int:
    rows = []
    for d in [d for d in disclosures if d.get("category") in NEWS_CATEGORIES][:limit]:
        for it in naver.search_news(names.get(d["code"], d["code"]), display=3):
            if it["url"]:
                rows.append({"code": d["code"], "rcept_no": d["rcept_no"], "source": None, **it})
    return store.upsert("news", rows)


# ── 6. 분석 → 결과 테이블 ─────────────────────────────────────
UNIVERSE_SQL = {
    "companies": "select code, corp_code, name, market, ksic, ksic_name, themes, is_financial from companies",
    "prices": "select date, code, open, high, low, close, volume, market_cap, shares from prices_daily where date >= %(since)s",
    "kospi": "select date, kospi from index_daily where kospi is not null and date >= %(since)s order by date",
    "financials": "select * from financials order by code, year, quarter",
    "disclosures": "select rcept_no, code, report_nm, rcept_dt, first_seen_at, detail from disclosures where rcept_dt >= %(since)s",
    "annual": "select distinct on (code) code, year, dividend_total, audit_opinion from annual_facts order by code, year desc",
}


def universe_from_db(store, since: date, as_of: date) -> Universe:
    q = {k: store.read_df(sql, {"since": since}) for k, sql in UNIVERSE_SQL.items()}
    companies = q["companies"].to_dict("records")
    for c in companies:
        c["themes"] = list(c.get("themes") or [])
    prices = q["prices"].astype({"close": float, "volume": float, "market_cap": float, "shares": float})
    kospi = pd.Series(q["kospi"]["kospi"].astype(float).values, index=pd.to_datetime(q["kospi"]["date"]))
    fin = q["financials"]
    quarters = {code: g.drop(columns=["code"]).reset_index(drop=True) for code, g in fin.groupby("code")}
    num_cols = [c for c in fin.columns if c not in ("code", "year", "quarter", "period_end", "available_from", "fs_div")]
    for code, g in quarters.items():
        quarters[code] = g.astype({c: float for c in num_cols if c in g})
    annual = q["annual"]
    dividends = {r["code"]: float(r["dividend_total"]) for r in annual.to_dict("records") if r["dividend_total"] is not None}
    audit_ok = {
        r["code"]: ("적정" in r["audit_opinion"] and "부적정" not in r["audit_opinion"]) for r in annual.to_dict("records") if r["audit_opinion"]
    }
    disc = q["disclosures"].to_dict("records")
    for d in disc:
        d["rcept_dt"] = pd.Timestamp(d["rcept_dt"]).date()
        d["first_seen_at"] = d["first_seen_at"].to_pydatetime() if isinstance(d["first_seen_at"], pd.Timestamp) else d["first_seen_at"]
    return Universe(companies, prices, kospi, quarters, disc, dividends, audit_ok, as_of)


def write_outputs(store, out: Outputs) -> None:
    store.upsert("index_daily", [{"date": r["date"], "kospi_ew": r["kospi_ew"]} for r in out.index_daily], update_columns=["kospi_ew"])
    store.upsert("disclosure_impacts", out.impacts)
    store.upsert("disclosure_stats", [{k: v for k, v in s.items()} for s in out.stats])
    store.upsert("scores", out.scores)
    store.upsert("valuation", out.valuation)
    store.upsert("valuation_history", out.valuation_history)
    fin_cols = {"code", "year", "quarter", "ttm_revenue", "ttm_operating_income", "ttm_net_income_parent", "roe", "op_margin", "debt_ratio"}
    store.upsert("financials", [{k: v for k, v in r.items() if k in fin_cols} for r in out.financials], update_columns=sorted(fin_cols))


def recompute(store, as_of: date, years: int = 5) -> Outputs:
    since = as_of - timedelta(days=365 * years + 30)
    u = universe_from_db(store, since, as_of)
    out = build(u)
    write_outputs(store, out)
    log.info("recomputed: %d impacts, %d stats, %d scores", len(out.impacts), len(out.stats), len(out.scores))
    return out
