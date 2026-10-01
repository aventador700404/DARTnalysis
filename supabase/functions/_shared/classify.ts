// 공시 제목 → 마커 유형. pipeline/dartpipe/classify.py 와 같은 규칙 (둘 중 하나를 바꾸면 같이 바꾸기).
// 의존성 없는 순수 함수라 Node·Deno 어디서든 실행 가능.

export type Category = "earnings" | "financing" | "buyback" | "ownership" | "other";

export interface Classification {
  category: Category;
  subtype: string | null;
  isCorrection: boolean;
}

const RULES: Array<[RegExp, Category, string]> = [
  [/유무상증자결정/, "financing", "rights_offering"],
  [/유상증자결정/, "financing", "rights_offering"],
  [/무상증자결정/, "financing", "bonus_issue"],
  [/감자결정/, "financing", "capital_reduction"],
  [/전환사채권발행결정/, "financing", "cb"],
  [/신주인수권부사채권발행결정/, "financing", "bw"],
  [/교환사채권발행결정/, "financing", "eb"],
  [/자기주식취득신탁계약/, "buyback", "buyback_trust"],
  [/자기주식취득결정/, "buyback", "buyback"],
  [/자기주식처분결정/, "buyback", "treasury_disposal"],
  [/자기주식소각/, "buyback", "cancellation"],
  [/주식등의대량보유상황보고서/, "ownership", "major_holder"],
  [/임원[ㆍ·]?주요주주특정증권등소유상황보고서/, "ownership", "insider"],
  [/최대주주변경/, "ownership", "largest_holder_change"],
  [/(사업|반기|분기)보고서/, "earnings", "periodic_report"],
  [/영업\(잠정\)실적|연결재무제표기준영업\(잠정\)실적/, "earnings", "preliminary_earnings"],
  [/매출액또는손익구조/, "earnings", "earnings_change"],
];

export function classify(reportNm: string): Classification {
  let name = (reportNm ?? "").trim();
  let isCorrection = false;
  const m = name.match(/^\[([^\]]+)\]/);
  if (m) {
    isCorrection = m[1].includes("정정");
    name = name.slice(m[0].length);
  }
  const compact = name.replace(/\s+/g, "");
  for (const [re, category, subtype] of RULES) {
    if (re.test(compact)) return { category, subtype, isCorrection };
  }
  return { category: "other", subtype: null, isCorrection };
}
