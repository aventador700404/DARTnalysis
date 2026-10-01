// 실제 데이터 (Supabase, 읽기 전용 anon 키 + RLS)
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
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

let client: SupabaseClient | null = null;
function db(): SupabaseClient {
  if (!client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) throw new Error("NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 필요합니다 (web/.env.example 참고)");
    client = createClient(url, key, { auth: { persistSession: false } });
  }
  return client;
}

const PAGE = 1000; // Supabase API는 한 번에 최대 1,000행

// 1,000행이 넘는 결과를 나눠서 모두 가져오기
async function fetchAll<T>(build: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: unknown }>): Promise<T[]> {
  const out: T[] = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await build(from, from + PAGE - 1);
    if (error) throw error;
    out.push(...(data ?? []));
    if (!data || data.length < PAGE) return out;
  }
}

const num = (v: unknown): number | null => (v == null ? null : Number(v));

async function latestDate(): Promise<string> {
  const { data, error } = await db().from("index_daily").select("date").order("date", { ascending: false }).limit(1);
  if (error) throw error;
  return data?.[0]?.date ?? new Date().toISOString().slice(0, 10);
}

function shiftDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

async function meta(): Promise<Meta> {
  return { demo: false, source: "supabase", asOf: await latestDate() };
}

export async function listCompanies(): Promise<Company[]> {
  return fetchAll<Company>((f, t) => db().from("companies").select("code, name, market, ksic, ksic_name, themes, is_financial").order("code").range(f, t));
}

/** 전 종목 최근 종가·전일 대비 */
async function quotes(companies: Company[], asOf: string): Promise<Map<string, Quote>> {
  const rows = await fetchAll<{ code: string; date: string; close: number; market_cap: number }>((f, t) =>
    db().from("prices_daily").select("code, date, close, market_cap").gte("date", shiftDays(asOf, -10)).order("date").range(f, t),
  );
  const by = new Map<string, typeof rows>();
  for (const r of rows) by.set(r.code, [...(by.get(r.code) ?? []), r]);
  const out = new Map<string, Quote>();
  for (const c of companies) {
    const s = by.get(c.code) ?? [];
    const last = s[s.length - 1];
    const prev = s[s.length - 2];
    out.set(c.code, {
      company: c,
      close: num(last?.close),
      change1d: last && prev ? Number(last.close) / Number(prev.close) - 1 : null,
      marketCap: num(last?.market_cap),
    });
  }
  return out;
}

const DISCLOSURE_COLS =
  "rcept_no, code, report_nm, rcept_dt, first_seen_at, category, subtype, group_key, is_correction, disclosure_impacts(base_date, excluded_reason, impact, notable, ret_5, ret_20, ex_kospi_5, ex_kospi_20, ex_ew_5, ex_ew_20)";

type DisclosureRow = Omit<Disclosure, "base_date" | "excluded_reason" | "impact" | "notable" | "ret_5" | "ret_20" | "ex_kospi_5" | "ex_kospi_20" | "ex_ew_5" | "ex_ew_20"> & {
  disclosure_impacts: Partial<Disclosure> | Partial<Disclosure>[] | null;
};

function flatten(r: DisclosureRow): Disclosure {
  const imp = Array.isArray(r.disclosure_impacts) ? r.disclosure_impacts[0] : r.disclosure_impacts;
  const { disclosure_impacts: _, ...rest } = r;
  void _;
  return {
    ...rest,
    base_date: imp?.base_date ?? null,
    excluded_reason: imp?.excluded_reason ?? null,
    impact: imp?.impact ?? null,
    notable: imp?.notable ?? false,
    ret_5: num(imp?.ret_5),
    ret_20: num(imp?.ret_20),
    ex_kospi_5: num(imp?.ex_kospi_5),
    ex_kospi_20: num(imp?.ex_kospi_20),
    ex_ew_5: num(imp?.ex_ew_5),
    ex_ew_20: num(imp?.ex_ew_20),
  };
}

async function stats(): Promise<StatRow[]> {
  const { data, error } = await db().from("disclosure_stats").select("*");
  if (error) throw error;
  return (data ?? []).map((s) => ({ ...s, mean: num(s.mean), median: num(s.median), up_ratio: num(s.up_ratio), p10: num(s.p10), p25: num(s.p25), p75: num(s.p75), p90: num(s.p90) }));
}

export async function getHome(): Promise<HomeData> {
  const m = await meta();
  const companies = await listCompanies();
  const nameOf = new Map(companies.map((c) => [c.code, c.name]));
  const named = (d: Disclosure): FeedItem => ({ ...d, company_name: nameOf.get(d.code) ?? d.code });

  const feedQ = db().from("disclosures").select(DISCLOSURE_COLS).order("rcept_dt", { ascending: false }).order("first_seen_at", { ascending: false }).limit(40);
  const notableQ = db()
    .from("disclosures")
    .select(DISCLOSURE_COLS.replace("disclosure_impacts(", "disclosure_impacts!inner("))
    .eq("disclosure_impacts.notable", true)
    .gte("rcept_dt", shiftDays(m.asOf, -120))
    .order("rcept_dt", { ascending: false })
    .limit(8);
  const indexQ = db().from("index_daily").select("date, kospi, kospi_ew").gte("date", shiftDays(m.asOf, -365)).order("date");
  const [feed, notable, index, q, st] = await Promise.all([feedQ, notableQ, indexQ, quotes(companies, m.asOf), stats()]);
  if (feed.error) throw feed.error;
  if (notable.error) throw notable.error;
  if (index.error) throw index.error;

  const themes = new Map<string, Quote[]>();
  for (const quote of q.values()) {
    const t = quote.company.themes?.[0];
    if (!t) continue; // 테마 미지정 종목은 히트맵에서 제외
    themes.set(t, [...(themes.get(t) ?? []), quote]);
  }
  return {
    meta: m,
    feed: (feed.data as unknown as DisclosureRow[]).map(flatten).map(named),
    notable: (notable.data as unknown as DisclosureRow[]).map(flatten).map(named),
    market: {
      dates: (index.data ?? []).map((r) => r.date),
      kospi: (index.data ?? []).map((r) => num(r.kospi)),
      ew: (index.data ?? []).map((r) => num(r.kospi_ew)),
    },
    themes: [...themes.entries()].map(([theme, members]) => ({ theme, members: members.sort((a, b) => (b.marketCap ?? 0) - (a.marketCap ?? 0)).slice(0, 12) })),
    stats: st,
  };
}

export async function getStock(code: string): Promise<StockBundle | null> {
  const m = await meta();
  const { data: company } = await db().from("companies").select("code, name, market, ksic, ksic_name, themes, is_financial").eq("code", code).maybeSingle();
  if (!company) return null;
  const since = shiftDays(m.asOf, -365 * 5);

  const [prices, index, disc, st, score, valuation, vh, fin, news] = await Promise.all([
    fetchAll<{ date: string; close: number; volume: number }>((f, t) => db().from("prices_daily").select("date, close, volume").eq("code", code).gte("date", since).order("date").range(f, t)),
    fetchAll<{ date: string; kospi: number; kospi_ew: number }>((f, t) => db().from("index_daily").select("date, kospi, kospi_ew").gte("date", since).order("date").range(f, t)),
    fetchAll<DisclosureRow>((f, t) => db().from("disclosures").select(DISCLOSURE_COLS).eq("code", code).order("rcept_dt", { ascending: false }).range(f, t) as never),
    stats(),
    db().from("scores").select("*").eq("code", code).maybeSingle(),
    db().from("valuation").select("*").eq("code", code).maybeSingle(),
    db().from("valuation_history").select("date, per, pbr").eq("code", code).order("date"),
    db().from("financials").select("year, quarter, period_end, available_from, revenue, operating_income, net_income_parent, op_margin, roe, debt_ratio, ttm_revenue, ttm_operating_income").eq("code", code).order("year").order("quarter"),
    db().from("news").select("code, rcept_no, title, url, source, published_at").eq("code", code).order("published_at", { ascending: false }).limit(30),
  ]);

  // 주가와 지수를 같은 날짜 축으로 맞추기
  const idx = new Map(index.map((r) => [r.date, r]));
  const dates = prices.map((p) => p.date);
  const peerGroup = (company.themes as string[])?.[0] ?? null;
  const peerCompanies: Company[] = peerGroup
    ? ((await db().from("companies").select("code, name, market, ksic, ksic_name, themes, is_financial").contains("themes", [peerGroup])).data ?? [])
    : [];
  const peerCodes = peerCompanies.map((c) => c.code);
  const [pv, ps, pq] = await Promise.all([
    db().from("valuation").select("*").in("code", peerCodes),
    db().from("scores").select("*").in("code", peerCodes),
    quotes(peerCompanies, m.asOf),
  ]);
  const vBy = new Map((pv.data ?? []).map((v) => [v.code, v as Valuation]));
  const sBy = new Map((ps.data ?? []).map((s) => [s.code, s as Score]));
  const peers: PeerRow[] = peerCompanies.map((c) => ({
    company: c,
    valuation: vBy.get(c.code) ?? null,
    score: sBy.get(c.code) ?? null,
    change1d: pq.get(c.code)?.change1d ?? null,
    isSelf: c.code === code,
  }));
  const selfQuote = (await quotes([company as Company], m.asOf)).get(code)!;

  return {
    meta: m,
    company: company as Company,
    quote: selfQuote,
    series: {
      dates,
      close: prices.map((p) => num(p.close)),
      volume: prices.map((p) => num(p.volume)),
      kospi: dates.map((d) => num(idx.get(d)?.kospi)),
      ew: dates.map((d) => num(idx.get(d)?.kospi_ew)),
    },
    disclosures: disc.map(flatten),
    stats: st,
    score: (score.data as Score) ?? null,
    valuation: (valuation.data as Valuation) ?? null,
    valuationHistory: {
      dates: (vh.data ?? []).map((r) => r.date),
      per: (vh.data ?? []).map((r) => num(r.per)),
      pbr: (vh.data ?? []).map((r) => num(r.pbr)),
    },
    financials: (fin.data ?? []) as FinancialQuarter[],
    peers,
    peerGroup,
    news: (news.data ?? []) as NewsItem[],
  };
}

export async function getSectors(): Promise<SectorData> {
  const m = await meta();
  const companies = await listCompanies();
  const [v, s, q] = await Promise.all([
    fetchAll<Valuation>((f, t) => db().from("valuation").select("*").range(f, t)),
    fetchAll<Score>((f, t) => db().from("scores").select("*").range(f, t)),
    quotes(companies, m.asOf),
  ]);
  const vBy = new Map(v.map((x) => [x.code, x]));
  const sBy = new Map(s.map((x) => [x.code, x]));
  return {
    meta: m,
    rows: companies.map((c) => ({ company: c, valuation: vBy.get(c.code) ?? null, score: sBy.get(c.code) ?? null, change1d: q.get(c.code)?.change1d ?? null })),
  };
}
