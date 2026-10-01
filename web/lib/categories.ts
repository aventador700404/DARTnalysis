import type { CategoryKey } from "./types";

// 마커 유형 5종 (pipeline/dartpipe/classify.py CATEGORIES와 같음)
// 차트에서 두 줄로 나눠 찍는다 → 같은 줄 안의 색끼리만 구분되면 됨.
//   위(above): 자금조달 주황 · 자사주 청록 · 기타 회색   /   아래(below): 실적 파랑 · 지분 변동 노랑
// 각 줄의 색 조합은 dataviz 검증 스크립트로 색약(CVD)·정상 시각 구분 기준을 통과한 것 (README 참고).
export const CATEGORIES: { key: CategoryKey; label: string; short: string; color: string; row: "above" | "below" }[] = [
  { key: "earnings", label: "실적·정기보고서", short: "실", color: "var(--cat-earnings)", row: "below" },
  { key: "financing", label: "자금조달 (증자·CB)", short: "증", color: "var(--cat-financing)", row: "above" },
  { key: "buyback", label: "자사주", short: "자", color: "var(--cat-buyback)", row: "above" },
  { key: "ownership", label: "지분 변동", short: "지", color: "var(--cat-ownership)", row: "below" },
  { key: "other", label: "기타", short: "기", color: "var(--cat-other)", row: "above" },
];

export const CATEGORY_BY_KEY = Object.fromEntries(CATEGORIES.map((c) => [c.key, c])) as Record<
  CategoryKey,
  (typeof CATEGORIES)[number]
>;

export const SUBTYPE_LABELS: Record<string, string> = {
  rights_offering: "유상증자",
  bonus_issue: "무상증자",
  capital_reduction: "감자",
  cb: "전환사채 발행",
  bw: "신주인수권부사채 발행",
  eb: "교환사채 발행",
  buyback: "자사주 취득",
  buyback_trust: "자사주 신탁계약",
  treasury_disposal: "자사주 처분",
  cancellation: "자사주 소각",
  major_holder: "5% 대량보유 보고",
  insider: "임원·주요주주 지분 보고",
  largest_holder_change: "최대주주 변경",
  periodic_report: "정기보고서",
  preliminary_earnings: "잠정실적",
  earnings_change: "손익구조 30% 이상 변동",
};

export function groupLabel(groupKey: string): string {
  return SUBTYPE_LABELS[groupKey] ?? CATEGORY_BY_KEY[groupKey as CategoryKey]?.label ?? groupKey;
}

export const AXES = [
  { key: "growth", label: "성장성", desc: "매출·영업이익 3년 연평균 성장률" },
  { key: "profitability", label: "수익성", desc: "ROE, 영업이익률" },
  { key: "stability", label: "안정성", desc: "부채비율, 이자보상배율, 감사의견" },
  { key: "value", label: "가격", desc: "PER·PBR (업종 대비, 과거 5년 대비) · 낮을수록 높은 점수" },
  { key: "shareholder_return", label: "주주환원", desc: "배당수익률, 자사주 매입 규모" },
] as const;

export const METRIC_LABELS: Record<string, { label: string; format: "pct" | "x" | "pctile" | "times" }> = {
  revenue_cagr_3y: { label: "매출 3년 연평균 성장률", format: "pct" },
  op_income_cagr_3y: { label: "영업이익 3년 연평균 성장률", format: "pct" },
  roe: { label: "ROE", format: "pct" },
  op_margin: { label: "영업이익률", format: "pct" },
  debt_ratio: { label: "부채비율", format: "pct" },
  interest_coverage: { label: "이자보상배율", format: "times" },
  per: { label: "PER", format: "x" },
  pbr: { label: "PBR", format: "x" },
  per_band_pct: { label: "PER 5년 범위 중 위치", format: "pctile" },
  dividend_yield: { label: "배당수익률", format: "pct" },
  buyback_yield: { label: "자사주 매입 / 시가총액 (1년)", format: "pct" },
};

export const AXIS_METRICS: Record<string, string[]> = {
  growth: ["revenue_cagr_3y", "op_income_cagr_3y"],
  profitability: ["roe", "op_margin"],
  stability: ["debt_ratio", "interest_coverage"],
  value: ["per", "pbr", "per_band_pct"],
  shareholder_return: ["dividend_yield", "buyback_yield"],
};
