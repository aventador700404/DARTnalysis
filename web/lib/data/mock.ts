// 가상 기업 샘플 데이터 (pipeline/dartpipe/mock/generate.py 가 만든 JSON) → 화면용 데이터
import raw from "@/lib/mock/data.json";
import type {
  Company,
  Disclosure,
  FeedItem,
  FinancialQuarter,
  HomeData,
  Meta,
  NewsItem,
  PeerRow,
  Quote,
  Score,
  SectorData,
  StatRow,
  StockBundle,
  Valuation,
} from "@/lib/types";

interface MockData {
  meta: { demo: boolean; as_of: string };
  companies: Company[];
  calendar: string[];
  prices: Record<string, { c: (number | null)[]; v: (number | null)[]; sh: (number | null)[] }>;
  index: { kospi: (number | null)[]; ew: (number | null)[] };
  disclosures: Disclosure[];
  stats: StatRow[];
  scores: Score[];
  valuation: Valuation[];
  valuation_history: Record<string, { d: string[]; per: (number | null)[]; pbr: (number | null)[] }>;
  financials: Record<string, FinancialQuarter[]>;
  news: NewsItem[];
}

const data = raw as unknown as MockData;

const meta: Meta = { demo: true, source: "mock", asOf: data.meta.as_of };
const companyBy = new Map(data.companies.map((c) => [c.code, c]));
const scoreBy = new Map(data.scores.map((s) => [s.code, s]));
const valuationBy = new Map(data.valuation.map((v) => [v.code, v]));
// 최신순: 접수일 → 처음 발견 시각 → 접수번호
const sortedDisclosures = [...data.disclosures].sort(
  (a, b) =>
    b.rcept_dt.localeCompare(a.rcept_dt) ||
    (b.first_seen_at ?? "").localeCompare(a.first_seen_at ?? "") ||
    b.rcept_no.localeCompare(a.rcept_no),
);

function quote(code: string): Quote {
  const company = companyBy.get(code)!;
  const p = data.prices[code];
  const n = p.c.length;
  const close = p.c[n - 1];
  const prev = p.c[n - 2];
  return {
    company,
    close,
    change1d: close != null && prev ? close / prev - 1 : null,
    marketCap: close != null && p.sh[n - 1] != null ? close * (p.sh[n - 1] as number) : null,
  };
}

function withName(d: Disclosure): FeedItem {
  return { ...d, company_name: companyBy.get(d.code)?.name ?? d.code };
}

export function listCompanies(): Company[] {
  return data.companies;
}

export function getHome(): HomeData {
  const cutoff = shiftDays(data.meta.as_of, -120);
  const quotes = data.companies.map((c) => quote(c.code));
  const themes = new Map<string, Quote[]>();
  for (const q of quotes) {
    const t = q.company.themes[0] ?? "기타";
    themes.set(t, [...(themes.get(t) ?? []), q]);
  }
  const start = Math.max(0, data.calendar.length - 250);
  return {
    meta,
    feed: sortedDisclosures.slice(0, 40).map(withName),
    notable: sortedDisclosures.filter((d) => d.notable && d.rcept_dt >= cutoff).slice(0, 8).map(withName),
    market: { dates: data.calendar.slice(start), kospi: data.index.kospi.slice(start), ew: data.index.ew.slice(start) },
    themes: [...themes.entries()].map(([theme, members]) => ({
      theme,
      members: members.sort((a, b) => (b.marketCap ?? 0) - (a.marketCap ?? 0)),
    })),
    stats: data.stats,
  };
}

export function getStock(code: string): StockBundle | null {
  const company = companyBy.get(code);
  if (!company) return null;
  const p = data.prices[code];
  const peerGroup = company.themes[0] ?? null;
  const peers: PeerRow[] = data.companies
    .filter((c) => peerGroup && c.themes.includes(peerGroup))
    .map((c) => ({
      company: c,
      valuation: valuationBy.get(c.code) ?? null,
      score: scoreBy.get(c.code) ?? null,
      change1d: quote(c.code).change1d,
      isSelf: c.code === code,
    }));
  const vh = data.valuation_history[code] ?? { d: [], per: [], pbr: [] };
  return {
    meta,
    company,
    quote: quote(code),
    series: { dates: data.calendar, close: p.c, volume: p.v, kospi: data.index.kospi, ew: data.index.ew },
    disclosures: sortedDisclosures.filter((d) => d.code === code),
    stats: data.stats,
    score: scoreBy.get(code) ?? null,
    valuation: valuationBy.get(code) ?? null,
    valuationHistory: { dates: vh.d, per: vh.per, pbr: vh.pbr },
    financials: data.financials[code] ?? [],
    peers,
    peerGroup,
    news: data.news.filter((n) => n.code === code).sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? "")),
  };
}

export function getSectors(): SectorData {
  return {
    meta,
    rows: data.companies.map((c) => ({
      company: c,
      valuation: valuationBy.get(c.code) ?? null,
      score: scoreBy.get(c.code) ?? null,
      change1d: quote(c.code).change1d,
    })),
  };
}

/** 데모 실시간 피드에 쓰는 '새 공시' 후보 (실제 과거 공시를 재사용) */
export function demoLivePool(): FeedItem[] {
  return sortedDisclosures
    .filter((d) => ["financing", "buyback", "ownership"].includes(d.category))
    .slice(0, 30)
    .map(withName);
}

function shiftDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
