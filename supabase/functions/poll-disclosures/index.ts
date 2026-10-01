// 1분마다 Supabase Cron이 호출 → 오늘 새로 올라온 코스피 공시를 DB에 넣는다.
// 새 행이 들어가면 Supabase Realtime이 브라우저로 바로 푸시 → 차트에 마커가 뜸.
//
// 필요한 비밀값 (supabase secrets set ...):
//   DART_API_KEY, CRON_SECRET, (선택) NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
// SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 는 Edge Function에 기본으로 들어 있음.
//
// 재무 영향(희석률 등)과 공시 후 수익률은 장 마감 후 일일 배치(파이썬)가 계산한다.

import { createClient } from "npm:@supabase/supabase-js@2";
import { classify } from "../_shared/classify.ts";

const DART_LIST = "https://opendart.fss.or.kr/api/list.json";
const NAVER_NEWS = "https://openapi.naver.com/v1/search/news.json";
const NEWS_CATEGORIES = new Set(["financing", "buyback", "ownership"]);
const MAX_PAGES = 10; // 한 번에 최대 1,000건

function kstToday(): string {
  const now = new Date(Date.now() + 9 * 3600 * 1000);
  return now.toISOString().slice(0, 10).replaceAll("-", "");
}

function toIsoDate(yyyymmdd: string): string {
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
}

interface DartItem {
  rcept_no: string;
  corp_code: string;
  corp_name: string;
  stock_code: string;
  report_nm: string;
  rcept_dt: string;
}

async function fetchTodayDisclosures(apiKey: string): Promise<{ items: DartItem[]; calls: number }> {
  const today = kstToday();
  const items: DartItem[] = [];
  let page = 1;
  let totalPage = 1;
  let calls = 0;
  do {
    const url = new URL(DART_LIST);
    url.search = new URLSearchParams({
      crtfc_key: apiKey,
      bgn_de: today,
      end_de: today,
      corp_cls: "Y",
      page_no: String(page),
      page_count: "100",
    }).toString();
    const res = await fetch(url);
    calls++;
    const body = await res.json();
    if (body.status === "013") break; // 오늘 공시 없음
    if (body.status !== "000") throw new Error(`DART ${body.status}: ${body.message}`);
    items.push(...body.list);
    totalPage = Number(body.total_page ?? 1);
    page++;
  } while (page <= totalPage && page <= MAX_PAGES);
  return { items, calls };
}

async function searchNews(name: string, id: string, secret: string) {
  const url = new URL(NAVER_NEWS);
  url.search = new URLSearchParams({ query: name, display: "3", sort: "date" }).toString();
  const res = await fetch(url, { headers: { "X-Naver-Client-Id": id, "X-Naver-Client-Secret": secret } });
  if (!res.ok) return [];
  const body = await res.json();
  const strip = (s: string) => s.replace(/<[^>]+>/g, "").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&#39;/g, "'");
  return (body.items ?? []).map((it: Record<string, string>) => ({
    title: strip(it.title),
    summary: strip(it.description),
    url: it.originallink || it.link,
    published_at: new Date(it.pubDate).toISOString(),
  }));
}

Deno.serve(async (req) => {
  if (req.headers.get("x-cron-secret") !== Deno.env.get("CRON_SECRET")) {
    return new Response("forbidden", { status: 403 });
  }
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false },
  });

  // 우리가 추적하는 종목(코스피 보통주)만. API는 한 번에 최대 1,000행이라 나눠서 읽기
  const nameOf = new Map<string, string>();
  for (let from = 0; ; from += 1000) {
    const { data, error: compErr } = await supabase.from("companies").select("code, name").order("code").range(from, from + 999);
    if (compErr) return Response.json({ error: compErr.message }, { status: 500 });
    for (const c of data ?? []) nameOf.set(c.code, c.name);
    if (!data || data.length < 1000) break;
  }

  const { items, calls } = await fetchTodayDisclosures(Deno.env.get("DART_API_KEY")!);
  const rows = items
    .filter((it) => nameOf.has(it.stock_code?.trim()))
    .map((it) => {
      const c = classify(it.report_nm);
      return {
        rcept_no: it.rcept_no,
        code: it.stock_code.trim(),
        corp_code: it.corp_code,
        report_nm: it.report_nm.trim(),
        rcept_dt: toIsoDate(it.rcept_dt),
        category: c.category,
        subtype: c.subtype,
        group_key: c.subtype ?? c.category,
        is_correction: c.isCorrection,
        news_followup_at: NEWS_CATEGORIES.has(c.category) ? new Date(Date.now() + 30 * 60 * 1000).toISOString() : null,
      };
    });

  // 이미 있는 공시는 무시 → first_seen_at(기본값 now())은 처음 넣을 때만 기록됨
  const { data: inserted, error } = await supabase
    .from("disclosures")
    .upsert(rows, { onConflict: "rcept_no", ignoreDuplicates: true })
    .select("rcept_no, code, category");
  if (error) return Response.json({ error: error.message }, { status: 500 });

  // 뉴스: 새로 들어온 주요 공시 + 30분 지난 재검색 대상
  let newsCalls = 0;
  const naverId = Deno.env.get("NAVER_CLIENT_ID");
  const naverSecret = Deno.env.get("NAVER_CLIENT_SECRET");
  if (naverId && naverSecret) {
    const { data: followups } = await supabase
      .from("disclosures")
      .select("rcept_no, code, category")
      .lte("news_followup_at", new Date().toISOString())
      .limit(10);
    const targets = [...(inserted ?? []).filter((d) => NEWS_CATEGORIES.has(d.category)), ...(followups ?? [])].slice(0, 15);
    for (const d of targets) {
      const news = await searchNews(nameOf.get(d.code) ?? d.code, naverId, naverSecret);
      newsCalls++;
      if (news.length) {
        await supabase.from("news").upsert(
          news.map((n: Record<string, string>) => ({ ...n, code: d.code, rcept_no: d.rcept_no, source: "네이버 뉴스 검색" })),
          { onConflict: "url", ignoreDuplicates: true },
        );
      }
    }
    if (followups?.length) {
      await supabase.from("disclosures").update({ news_followup_at: null }).in("rcept_no", followups.map((f) => f.rcept_no));
    }
  }

  // 호출 수 기록 (한도 관리)
  const day = toIsoDate(kstToday());
  await supabase.rpc("bump_api_usage", { p_day: day, p_api: "dart", p_calls: calls });
  if (newsCalls) await supabase.rpc("bump_api_usage", { p_day: day, p_api: "naver", p_calls: newsCalls });

  return Response.json({ checked: items.length, inserted: inserted?.length ?? 0, dartCalls: calls, newsCalls });
});
