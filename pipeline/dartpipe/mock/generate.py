"""가상 기업 샘플 데이터 생성기 (웹 데모용).

- 실제 회사·실제 공시가 아닌 **가상 기업**과 가상 공시를 만든다 (종목코드도 X로 시작하는 가짜 코드).
- 재무는 OpenDART 응답과 같은 모양(분·반기 누적 포함)으로 만든 뒤, 실제 파이프라인 함수
  (financials → analyze)로 다시 읽어서 계산한다. 즉 샘플 화면의 숫자도 실제 로직으로 계산된 값.

실행:  python -m dartpipe.mock.generate   →  web/lib/mock/data.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import config
from ..analyze import Universe, build
from ..classify import CATEGORIES
from ..clients.dart import REPRT_ANNUAL, REPRT_H1, REPRT_Q1, REPRT_Q3
from ..financials import ACCOUNTS, extract_report, quarterize_year

KST = ZoneInfo("Asia/Seoul")
OUT = config.REPO_ROOT / "web" / "lib" / "mock" / "data.json"
AS_OF = date(2026, 9, 30)
PRICE_START = date(2023, 7, 3)
FIN_START_YEAR = 2021

THEMES = {
    "semiconductor": "반도체",
    "battery": "2차전지",
    "auto": "자동차",
    "platform": "인터넷·플랫폼",
}


@dataclass
class Spec:
    code: str
    name: str
    theme: str
    ksic: str
    ksic_name: str
    price0: float
    shares: float
    revenue0: float  # 2021년 연간 매출(원)
    growth: float  # 연 성장률
    margin: float  # 영업이익률
    debt_ratio: float
    payout: float
    vol: float
    cb_rate: float = 0.1
    rights_rate: float = 0.08


TARGET_PER = {"semiconductor": 13.0, "battery": 28.0, "auto": 6.5, "platform": 22.0}

EOK = 1e8
JO = 1e12

SPECS = [
    # 반도체 — 두 대형주가 '가상 코스피'의 절반 이상을 차지하도록 (실제 시장의 쏠림 재현)
    Spec("X00010", "한빛반도체", "semiconductor", "264", "통신 및 방송 장비 제조업", 71000, 5.9e9, 280 * JO, 0.08, 0.14, 0.35, 0.25, 0.017),
    Spec("X00030", "다온메모리", "semiconductor", "261", "반도체 제조업", 160000, 7.2e8, 45 * JO, 0.18, 0.22, 0.45, 0.15, 0.024),
    Spec("X00020", "누리실리콘", "semiconductor", "261", "반도체 제조업", 38000, 9.0e7, 1.9 * JO, 0.12, 0.11, 0.60, 0.20, 0.026),
    Spec("X00040", "세온테크", "semiconductor", "292", "특수 목적용 기계 제조업", 52000, 6.0e7, 0.9 * JO, 0.15, 0.16, 0.40, 0.18, 0.029, cb_rate=0.25),
    Spec("X00050", "미르소재", "semiconductor", "201", "기초 화학물질 제조업", 24500, 1.1e8, 1.2 * JO, 0.06, 0.08, 0.85, 0.30, 0.024),
    # 2차전지
    Spec("X00060", "가람에너지", "battery", "282", "일차전지 및 축전지 제조업", 410000, 2.3e8, 25 * JO, 0.10, 0.05, 1.10, 0.10, 0.026, rights_rate=0.3),
    Spec("X00070", "단비배터리", "battery", "282", "일차전지 및 축전지 제조업", 290000, 6.9e7, 19 * JO, 0.07, 0.03, 1.40, 0.05, 0.029, cb_rate=0.3),
    Spec("X00080", "솔내화학", "battery", "201", "기초 화학물질 제조업", 320000, 7.0e7, 42 * JO, 0.03, 0.04, 0.95, 0.25, 0.024),
    Spec("X00090", "하늘소재", "battery", "202", "기타 화학제품 제조업", 98000, 9.5e7, 3.8 * JO, 0.09, 0.06, 1.20, 0.12, 0.031, cb_rate=0.35, rights_rate=0.25),
    Spec("X00100", "온새미셀", "battery", "282", "일차전지 및 축전지 제조업", 21000, 1.4e8, 1.1 * JO, 0.02, 0.02, 1.80, 0.00, 0.034, cb_rate=0.45, rights_rate=0.35),
    # 자동차
    Spec("X00110", "바름모터스", "auto", "301", "자동차용 엔진 및 자동차 제조업", 205000, 2.6e8, 120 * JO, 0.06, 0.08, 1.50, 0.25, 0.017),
    Spec("X00120", "새솔부품", "auto", "303", "자동차 신품 부품 제조업", 230000, 9.4e7, 50 * JO, 0.05, 0.06, 0.70, 0.25, 0.017),
    Spec("X00130", "이든오토", "auto", "303", "자동차 신품 부품 제조업", 18500, 1.2e8, 3.1 * JO, 0.04, 0.05, 1.00, 0.30, 0.020),
    Spec("X00140", "다래모빌리티", "auto", "301", "자동차용 엔진 및 자동차 제조업", 94000, 4.0e8, 85 * JO, 0.07, 0.09, 1.20, 0.30, 0.019),
    # 인터넷·플랫폼
    Spec("X00150", "모아랩스", "platform", "631", "자료 처리, 호스팅, 포털 및 기타 인터넷 정보 매개 서비스업", 185000, 1.6e8, 8.5 * JO, 0.09, 0.15, 0.45, 0.20, 0.022),
    Spec("X00160", "너울커머스", "platform", "479", "기타 무점포 소매업", 52000, 4.4e8, 6.8 * JO, 0.12, 0.07, 0.70, 0.05, 0.025),
    Spec("X00170", "별빛게임즈", "platform", "582", "소프트웨어 개발 및 공급업", 33000, 7.0e7, 0.8 * JO, 0.01, 0.10, 0.35, 0.10, 0.030, cb_rate=0.2),
    Spec("X00180", "아라페이", "platform", "620", "컴퓨터 프로그래밍, 시스템 통합 및 관리업", 26500, 4.5e8, 1.4 * JO, 0.15, 0.03, 0.60, 0.00, 0.028),
]

# 공시 종류: (report_nm, 연 발생률, 기준일부터 5거래일 동안의 평균 초과수익률)
EVENT_TYPES = {
    "buyback": ("주요사항보고서(자기주식취득결정)", 0.7, 0.024),
    "treasury_disposal": ("주요사항보고서(자기주식처분결정)", 0.25, -0.014),
    "major_holder": ("주식등의대량보유상황보고서(일반)", 0.9, 0.004),
    "insider": ("임원ㆍ주요주주특정증권등소유상황보고서", 1.6, 0.0),
    "contract": ("단일판매ㆍ공급계약체결", 1.4, 0.012),
    "investment": ("타법인주식및출자증권취득결정", 0.5, -0.003),
    "lawsuit": ("소송등의제기ㆍ신청(일정금액이상의청구)", 0.25, -0.006),
    "prelim": ("연결재무제표기준영업(잠정)실적(공정공시)", 0.0, 0.0),  # 분기마다 별도 생성
}


def trading_calendar(start: date, end: date) -> pd.DatetimeIndex:
    days = pd.bdate_range(start, end)
    holidays = {date(y, m, d) for y in range(2023, 2027) for (m, d) in ((1, 1), (3, 1), (5, 5), (6, 6), (8, 15), (10, 3), (10, 9), (12, 25))}
    return pd.DatetimeIndex([d for d in days if d.date() not in holidays])


def report_dates(year: int) -> dict[int, date]:
    """분기 → 정기보고서 공시일 (법정 기한 근처)."""
    return {1: date(year, 5, 14), 2: date(year, 8, 13), 3: date(year, 11, 13), 4: date(year + 1, 3, 12)}


class Generator:
    def __init__(self, seed: int = 7):
        self.rng = np.random.default_rng(seed)
        self.cal = trading_calendar(PRICE_START, AS_OF)
        self.seq = 0
        self.quarterly_truth_cache: dict[str, list[dict]] = {}

    def rcept_no(self, d: date) -> str:
        self.seq += 1
        return f"{d:%Y%m%d}9{self.seq:05d}"  # 9로 시작하는 가짜 일련번호

    # ── 재무 (DART 응답 모양으로) ───────────────────────────
    def truth(self, s: Spec) -> list[dict]:
        if s.code not in self.quarterly_truth_cache:
            self.quarterly_truth_cache[s.code] = self.quarterly_truth(s)
        return self.quarterly_truth_cache[s.code]

    def quarterly_truth(self, s: Spec) -> list[dict]:
        rng = self.rng
        rows = []
        equity = s.revenue0 * 0.9
        season = np.array([0.94, 1.0, 1.01, 1.05])
        for year in range(FIN_START_YEAR, AS_OF.year + 1):
            annual = s.revenue0 * (1 + s.growth) ** (year - FIN_START_YEAR)
            for q in range(1, 5):
                cycle = 1 + 0.12 * np.sin((year - 2021) * 2.1 + q * 0.9) if s.theme in ("semiconductor", "battery") else 1.0
                rev = annual / 4 * season[q - 1] * cycle * rng.normal(1, 0.03)
                margin = s.margin * cycle * rng.normal(1, 0.18) + (0.02 if s.theme == "semiconductor" and year >= 2025 else 0)
                op = rev * margin
                interest = rev * 0.006 * s.debt_ratio
                ni = (op - interest) * 0.78
                ni_parent = ni * 0.97
                equity += ni_parent * (1 - s.payout)
                liabilities = equity * s.debt_ratio * rng.normal(1, 0.03)
                ocf = (ni + rev * 0.05) * rng.normal(1, 0.15)
                rows.append(
                    {
                        "year": year,
                        "quarter": q,
                        "revenue": rev,
                        "operating_income": op,
                        "net_income": ni,
                        "net_income_parent": ni_parent,
                        "interest_expense": interest,
                        "operating_cash_flow": ocf,
                        "total_equity": equity / 0.97,
                        "equity_parent": equity,
                        "total_liabilities": liabilities,
                        "total_assets": liabilities + equity / 0.97,
                    }
                )
        return rows

    @staticmethod
    def dart_rows(truth: list[dict], year: int) -> dict[str, list[dict]]:
        """분기 실제 값 → 보고서별 fnlttSinglAcntAll 행 (분·반기 누적 규칙 재현)."""
        by_q = {r["quarter"]: r for r in truth if r["year"] == year}
        out: dict[str, list[dict]] = {}
        for code, q in ((REPRT_Q1, 1), (REPRT_H1, 2), (REPRT_Q3, 3), (REPRT_ANNUAL, 4)):
            if q not in by_q:
                continue
            rows = []
            for item, (sj_divs, ids, names) in ACCOUNTS.items():
                sj = sj_divs[0]
                cum = sum(by_q[k][item] for k in range(1, q + 1)) if sj != "BS" else None
                if sj == "BS":
                    thstrm, add = by_q[q][item], None
                elif sj == "CF":
                    thstrm, add = cum, None  # 현금흐름표는 누적만
                elif code == REPRT_ANNUAL:
                    thstrm, add = cum, None  # 사업보고서는 연간 값만
                elif code == REPRT_Q1:
                    thstrm, add = by_q[1][item], by_q[1][item]
                else:
                    thstrm, add = by_q[q][item], cum
                rows.append(
                    {
                        "sj_div": sj,
                        "account_id": ids[0],
                        "account_nm": names[0],
                        "thstrm_amount": f"{thstrm:.0f}",
                        "thstrm_add_amount": "" if add is None else f"{add:.0f}",
                    }
                )
            out[code] = rows
        return out

    def financial_quarters(self, s: Spec) -> pd.DataFrame:
        truth = self.truth(s)
        records = []
        for year in range(FIN_START_YEAR, AS_OF.year + 1):
            reports = {code: extract_report(rows) for code, rows in self.dart_rows(truth, year).items()}
            for q, vals in quarterize_year(reports).items():
                avail = report_dates(year)[q]
                if avail > AS_OF:
                    continue
                period_end = date(year, q * 3, 30 if q in (2, 3) else 31)
                records.append({"year": year, "quarter": q, "period_end": period_end.isoformat(), "available_from": avail.isoformat(), **vals})
        return pd.DataFrame(records)

    # ── 공시 ────────────────────────────────────────────────
    def seen_at(self, d: date) -> str | None:
        if (AS_OF - d).days > 120:
            return None  # 오래된 공시는 발견 시각을 모른다고 가정 (실제 백필과 동일)
        minutes = int(self.rng.integers(7 * 60 + 30, 18 * 60 + 50))
        return datetime.combine(d, time(minutes // 60, minutes % 60), KST).isoformat()

    def detail(self, kind: str, s: Spec, close: float) -> dict | None:
        rng = self.rng
        sh = s.shares
        if kind == "buyback":
            qty = sh * rng.uniform(0.003, 0.025)
            return {"aqpln_stk_ostk": f"{qty:.0f}", "aqpln_prc_ostk": f"{qty * close:.0f}", "aq_mth": "유가증권시장을 통한 장내 직접 취득", "aqexpd_bgd": "", "aqexpd_edd": ""}
        if kind == "treasury_disposal":
            qty = sh * rng.uniform(0.002, 0.01)
            return {"dppln_stk_ostk": f"{qty:.0f}", "dppln_prc_ostk": f"{qty * close:.0f}"}
        if kind == "rights_offering":
            new = sh * rng.uniform(0.06, 0.22)
            return {"nstk_ostk_cnt": f"{new:.0f}", "bfic_tisstk_ostk": f"{sh:.0f}", "fdpp_fclt": f"{new * close * 0.55:.0f}", "fdpp_op": f"{new * close * 0.45:.0f}", "ic_mthn": "주주배정후 실권주 일반공모"}
        if kind == "cb":
            ratio = rng.uniform(2, 14)
            face = sh * ratio / 100 * close
            return {"bd_fta": f"{face:.0f}", "cv_prc": f"{close:.0f}", "cvisstk_cnt": f"{sh * ratio / 100:.0f}", "cvisstk_tisstk_vs": f"{ratio:.2f}"}
        if kind == "major_holder":
            chg = rng.normal(0, 1.2)
            return {"repror": rng.choice(["가상자산운용", "가상연기금", "가상인베스트먼트"]), "stkrt": f"{5 + abs(rng.normal(3, 2)):.2f}", "stkrt_irds": f"{chg:.2f}"}
        if kind == "insider":
            chg = rng.normal(0, 0.15)
            return {"repror": "가상임원", "sp_stock_lmp_rate": f"{abs(rng.normal(0.5, 0.4)):.2f}", "sp_stock_lmp_irds_rate": f"{chg:.2f}"}
        return None

    def run(self) -> tuple[Universe, list[dict]]:
        rng = self.rng
        cal = self.cal
        n = len(cal)
        def demeaned(mean: float, sd: float) -> np.ndarray:
            x = rng.normal(0, sd, n)
            return mean + (x - x.mean())  # 표본 평균이 목표값과 정확히 같도록 (시드에 따른 쏠림 방지)

        market = demeaned(0.00045 + 0.0085**2 / 2, 0.0085)
        theme_f = {t: demeaned(0.0, 0.0055) for t in THEMES}
        theme_f["semiconductor"] += 0.0007  # 반도체 강세장 재현 (대형주 쏠림)

        price_rows, disclosures, news = [], [], []
        quarters, dividends, audit_ok = {}, {}, {}
        companies = []

        for s in SPECS:
            companies.append(
                {
                    "code": s.code,
                    "corp_code": f"9{s.code[1:]}0",
                    "name": s.name,
                    "market": "KOSPI",
                    "ksic": s.ksic,
                    "ksic_name": s.ksic_name,
                    "themes": [THEMES[s.theme]] + (["반도체"] if s.code == "X00010" else []) + (["스마트폰"] if s.code == "X00010" else []),
                    "is_financial": False,
                }
            )
            companies[-1]["themes"] = list(dict.fromkeys(companies[-1]["themes"]))
            beta = rng.uniform(0.8, 1.3)
            idio_vol = s.vol * 0.6
            total_var = (beta * 0.0085) ** 2 + 0.0055**2 + idio_vol**2
            idio = rng.normal(total_var / 2, idio_vol, n)  # 변동성 손실(σ²/2) 보정
            abnormal = np.zeros(n)
            events: list[tuple[int, str, str]] = []  # (기준일 위치, kind, report_nm)

            def add_event(kind: str, report_nm: str, effect: float, pos: int | None = None):
                pos = int(rng.integers(5, n - 2)) if pos is None else pos
                events.append((pos, kind, report_nm))
                eff = effect * rng.normal(1, 0.9) + rng.normal(0, 0.01)
                weights = np.array([0.45, 0.2, 0.15, 0.1, 0.1])
                for k, w in enumerate(weights):
                    if pos + k < n:
                        abnormal[pos + k] += eff * w

            years = n / 250
            for kind, (nm, rate, eff) in EVENT_TYPES.items():
                if rate <= 0:
                    continue
                for _ in range(rng.poisson(rate * years)):
                    add_event(kind, nm, eff)
            for _ in range(rng.poisson(s.rights_rate * years)):
                add_event("rights_offering", "주요사항보고서(유상증자결정)", -0.065)
            if s.code in ("X00090", "X00100", "X00060"):  # 표본 5건 이상 확보 (데모용)
                add_event("rights_offering", "주요사항보고서(유상증자결정)", -0.065)
            for _ in range(rng.poisson(s.cb_rate * years)):
                add_event("cb", "주요사항보고서(전환사채권발행결정)", -0.03)

            # 정기보고서·잠정실적
            for year in range(PRICE_START.year - 1, AS_OF.year + 1):
                for q, d in report_dates(year).items():
                    if not (PRICE_START <= d <= AS_OF):
                        continue
                    pos = int(cal.searchsorted(pd.Timestamp(d)))
                    if pos >= n:
                        continue
                    name = {1: "분기보고서", 2: "반기보고서", 3: "분기보고서", 4: "사업보고서"}[q]
                    period = f"({year}.{q * 3:02d})"
                    events.append((pos, "periodic", f"{name} {period}"))
                    prelim_pos = max(pos - 25, 1)
                    add_event("prelim", EVENT_TYPES["prelim"][0], rng.normal(0, 0.02), prelim_pos)

            # 주가 (실제 종가처럼 수정되지 않은 가격, 상장주식 수는 유상증자 후 증가)
            # 시작 주가는 2023년 상반기 실적 기준 목표 PER에 맞춤
            truth = self.truth(s)
            ttm_ni = sum(r["net_income_parent"] for r in truth if (r["year"], r["quarter"]) in ((2022, 3), (2022, 4), (2023, 1), (2023, 2)))
            price0 = TARGET_PER[s.theme] * rng.uniform(0.8, 1.25) * ttm_ni / s.shares
            ret = beta * market + theme_f[s.theme] + idio + abnormal
            close = price0 * np.cumprod(1 + ret)
            close = np.maximum(close, 500)
            shares = np.full(n, s.shares)
            volume = (s.shares * rng.uniform(0.001, 0.004, n) * (1 + np.abs(ret) * 25)).round()

            events.sort()
            for pos, kind, nm in events:
                if kind == "rights_offering" and pos + 45 < n:
                    shares[pos + 45 :] *= 1 + rng.uniform(0.05, 0.15)  # 신주 상장 (약 2달 뒤)

            for i, d in enumerate(cal):
                price_rows.append({"date": d, "code": s.code, "close": float(round(close[i])), "volume": float(volume[i]), "shares": float(shares[i])})

            # 공시 레코드 (기준일 위치 → 접수일·발견 시각)
            for pos, kind, nm in events:
                base = cal[pos].date()
                # 기준일보다 하루 전 장 마감 후 접수된 것으로 기록 (보수적 규칙과 맞게)
                rcept = cal[pos - 1].date() if pos > 0 else base
                seen = self.seen_at(rcept)
                if seen:
                    # 최근 공시는 시각이 있으니, 장중 발견이면 그날이 기준일 → 접수일을 기준일로
                    if datetime.fromisoformat(seen).time() < time(15, 30):
                        rcept = base
                        seen = datetime.combine(base, datetime.fromisoformat(seen).time(), KST).isoformat()
                rcept_no = self.rcept_no(rcept)
                detail = self.detail(kind, s, float(close[max(pos - 1, 0)]))
                disclosures.append(
                    {"rcept_no": rcept_no, "code": s.code, "report_nm": nm, "rcept_dt": rcept, "first_seen_at": seen, "detail": detail}
                )
                if (AS_OF - rcept).days <= 150 and kind in ("buyback", "rights_offering", "cb", "contract", "prelim", "major_holder"):
                    news.extend(self.fake_news(s, kind, rcept_no, rcept))

            quarters[s.code] = self.financial_quarters(s)
            last_year = quarters[s.code]
            fy = last_year[(last_year["quarter"] == 4)].tail(1)
            dividends[s.code] = float(fy["net_income_parent"].iloc[0] * 4 * s.payout) if not fy.empty else 0.0
            audit_ok[s.code] = s.code != "X00100"

        prices = pd.DataFrame(price_rows)
        prices["market_cap"] = prices["close"] * prices["shares"]
        # 가상 코스피 = 시가총액 가중 (실제처럼 대형주 쏠림)
        cap = prices.pivot(index="date", columns="code", values="market_cap")
        px = prices.pivot(index="date", columns="code", values="close")
        sh = prices.pivot(index="date", columns="code", values="shares")
        daily = (px.pct_change() * cap.shift(1)).sum(axis=1) / cap.shift(1).sum(axis=1)
        # 유상증자 신주 상장일은 주식 수만 늘고 가격은 연속이라 문제 없음
        _ = sh
        kospi = 2600 * (1 + daily.fillna(0)).cumprod()

        u = Universe(
            companies=companies,
            prices=prices,
            kospi=kospi,
            quarters=quarters,
            disclosures=disclosures,
            dividends=dividends,
            audit_ok=audit_ok,
            as_of=AS_OF,
        )
        return u, news

    def fake_news(self, s: Spec, kind: str, rcept_no: str, d: date) -> list[dict]:
        templates = {
            "buyback": ["{n}, 자사주 매입 결정… 주주환원 강화", "{n} 자사주 취득에 증권가 \"수급 개선 기대\""],
            "rights_offering": ["{n}, 대규모 유상증자 결정… 주가 희석 우려", "{n} 유상증자에 개인 투자자 '술렁'"],
            "cb": ["{n}, 전환사채 발행 결정… 잠재 물량 부담", "{n} CB 발행, 시설투자 자금 마련"],
            "contract": ["{n}, 대형 공급계약 체결", "{n} 수주 공시… 실적 개선 신호"],
            "prelim": ["{n} 잠정실적 발표… 시장 예상과 비교하면", "{n} 분기 영업이익 공개"],
            "major_holder": ["가상자산운용, {n} 지분 변동 보고", "{n} 5% 대량보유 보고 나와"],
        }
        picks = self.rng.choice(templates[kind], size=int(self.rng.integers(1, 3)), replace=False)
        out = []
        for i, t in enumerate(picks):
            ts = datetime.combine(d, time(16, 10 + i * 17), KST)
            out.append({"code": s.code, "rcept_no": rcept_no, "title": t.format(n=s.name), "source": "가상뉴스", "url": None, "published_at": ts.isoformat()})
        return out


def to_web_json(u: Universe, news: list[dict]) -> dict:
    out = build(u)
    cal = sorted(u.prices["date"].unique())
    cal_s = [pd.Timestamp(d).date().isoformat() for d in cal]
    series = {}
    for code, g in u.prices.groupby("code"):
        g = g.set_index("date").reindex(cal)
        series[code] = {
            "c": [None if pd.isna(v) else int(v) for v in g["close"]],
            "v": [None if pd.isna(v) else int(v) for v in g["volume"]],
            "sh": [None if pd.isna(v) else int(v) for v in g["shares"]],
        }
    impacts = {r["rcept_no"]: r for r in out.impacts}
    disclosures = []
    for d in out.disclosures:
        imp = impacts.get(d["rcept_no"], {})
        disclosures.append({**d, **{k: v for k, v in imp.items() if k not in ("rcept_no", "code", "group_key")}})

    def r4(x):
        return None if x is None else round(x, 4)

    val_hist: dict[str, dict] = {}
    for row in out.valuation_history:
        h = val_hist.setdefault(row["code"], {"d": [], "per": [], "pbr": []})
        h["d"].append(row["date"])
        h["per"].append(None if row["per"] is None else round(row["per"], 2))
        h["pbr"].append(None if row["pbr"] is None else round(row["pbr"], 3))

    fin_keys = ["year", "quarter", "period_end", "available_from", "revenue", "operating_income", "net_income_parent", "op_margin", "roe", "debt_ratio", "ttm_revenue", "ttm_operating_income"]
    financials: dict[str, list] = {}
    for row in out.financials:
        financials.setdefault(row["code"], []).append({k: (r4(row.get(k)) if isinstance(row.get(k), float) and k in ("op_margin", "roe", "debt_ratio") else row.get(k)) for k in fin_keys})

    return {
        "meta": {
            "demo": True,
            "as_of": AS_OF.isoformat(),
            "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
            "note": "가상 기업·가상 공시로 만든 샘플 데이터입니다. 실제 기업·실제 공시와 무관합니다.",
            "categories": CATEGORIES,
        },
        "companies": u.companies,
        "calendar": cal_s,
        "prices": series,
        "index": {
            "kospi": [r4(r["kospi"]) for r in out.index_daily],
            "ew": [r4(r["kospi_ew"]) for r in out.index_daily],
        },
        "disclosures": disclosures,
        "stats": out.stats,
        "scores": out.scores,
        "valuation": out.valuation,
        "valuation_history": val_hist,
        "financials": financials,
        "news": news,
    }


def main() -> None:
    gen = Generator()
    u, news = gen.run()
    data = to_web_json(u, news)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_disc = len(data["disclosures"])
    print(f"wrote {OUT.relative_to(config.REPO_ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB, 기업 {len(data['companies'])}개, 공시 {n_disc}건)")


if __name__ == "__main__":
    main()
