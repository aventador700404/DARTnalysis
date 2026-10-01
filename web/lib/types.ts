// 화면에서 쓰는 데이터 모양. DB 테이블(supabase/migrations)과 가상 데이터(lib/mock/data.json)가 같은 모양.

export type CategoryKey = "earnings" | "financing" | "buyback" | "ownership" | "other";
export type Benchmark = "ew" | "kospi";
export type DataSource = "mock" | "supabase";

export interface Meta {
  demo: boolean;
  source: DataSource;
  asOf: string; // 데이터 기준일
}

export interface Company {
  code: string;
  name: string;
  market: string;
  ksic: string | null;
  ksic_name: string | null;
  themes: string[];
  is_financial: boolean;
}

export interface Impact {
  kind: string;
  headline: string;
  metrics: Record<string, number | string | null | (string | null)[]>;
  notable: boolean;
}

export interface Disclosure {
  rcept_no: string;
  code: string;
  report_nm: string;
  rcept_dt: string;
  first_seen_at: string | null;
  category: CategoryKey;
  subtype: string | null;
  group_key: string;
  is_correction: boolean;
  base_date: string | null;
  excluded_reason: string | null;
  impact: Impact | null;
  notable: boolean;
  ret_5: number | null;
  ret_20: number | null;
  ex_kospi_5: number | null;
  ex_kospi_20: number | null;
  ex_ew_5: number | null;
  ex_ew_20: number | null;
}

export interface StatRow {
  group_key: string;
  group_label: string;
  category: CategoryKey;
  horizon: number;
  benchmark: Benchmark;
  n: number;
  hidden: boolean;
  mean: number | null;
  median: number | null;
  up_ratio: number | null;
  p10: number | null;
  p25: number | null;
  p75: number | null;
  p90: number | null;
}

export type AxisKey = "growth" | "profitability" | "stability" | "value" | "shareholder_return";

export interface Score {
  code: string;
  as_of: string;
  growth: number | null;
  profitability: number | null;
  stability: number | null;
  value: number | null;
  shareholder_return: number | null;
  metric_scores: Record<string, number>;
  basis: Record<string, string>;
  note: string | null;
}

export interface Valuation {
  code: string;
  as_of: string;
  market_cap: number | null;
  per: number | null;
  pbr: number | null;
  per_band_pct: number | null;
  pbr_band_pct: number | null;
  roe: number | null;
  op_margin: number | null;
  debt_ratio: number | null;
  interest_coverage: number | null;
  revenue_cagr_3y: number | null;
  op_income_cagr_3y: number | null;
  dividend_yield: number | null;
  buyback_yield: number | null;
  ttm_revenue: number | null;
  ttm_operating_income: number | null;
}

export interface FinancialQuarter {
  year: number;
  quarter: number;
  period_end: string;
  available_from: string | null;
  revenue: number | null;
  operating_income: number | null;
  net_income_parent: number | null;
  op_margin: number | null;
  roe: number | null;
  debt_ratio: number | null;
  ttm_revenue: number | null;
  ttm_operating_income: number | null;
}

export interface NewsItem {
  code: string;
  rcept_no: string | null;
  title: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
}

export interface PriceSeries {
  dates: string[];
  close: (number | null)[];
  volume: (number | null)[];
  kospi: (number | null)[];
  ew: (number | null)[];
}

export interface Quote {
  company: Company;
  close: number | null;
  change1d: number | null;
  marketCap: number | null;
}

export interface PeerRow {
  company: Company;
  valuation: Valuation | null;
  score: Score | null;
  change1d: number | null;
  isSelf: boolean;
}

export interface StockBundle {
  meta: Meta;
  company: Company;
  quote: Quote;
  series: PriceSeries;
  disclosures: Disclosure[]; // 최신순
  stats: StatRow[];
  score: Score | null;
  valuation: Valuation | null;
  valuationHistory: { dates: string[]; per: (number | null)[]; pbr: (number | null)[] };
  financials: FinancialQuarter[];
  peers: PeerRow[];
  peerGroup: string | null;
  news: NewsItem[];
}

export interface FeedItem extends Disclosure {
  company_name: string;
}

export interface HomeData {
  meta: Meta;
  feed: FeedItem[];
  notable: FeedItem[];
  market: { dates: string[]; kospi: (number | null)[]; ew: (number | null)[] };
  themes: { theme: string; members: Quote[] }[];
  stats: StatRow[];
}

export interface SectorRow {
  company: Company;
  valuation: Valuation | null;
  score: Score | null;
  change1d: number | null;
}

export interface SectorData {
  meta: Meta;
  rows: SectorRow[];
}
