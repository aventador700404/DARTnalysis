import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StockView, type Tab, type ViewState } from "@/components/stock/StockView";
import type { ChartMode, Range } from "@/components/stock/PriceChart";
import { getStock } from "@/lib/data";
import type { Benchmark } from "@/lib/types";

export const revalidate = 300;

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const pick = <T extends string>(v: string | undefined, allowed: readonly T[], fallback: T): T => (v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback);

export async function generateMetadata({ params }: PageProps<"/stock/[code]">): Promise<Metadata> {
  const { code } = await params;
  const b = await getStock(code);
  return { title: b ? `${b.company.name} (${b.company.code})` : "종목을 찾을 수 없음" };
}

export default async function StockPage({ params, searchParams }: PageProps<"/stock/[code]">) {
  const { code } = await params;
  const sp = await searchParams;
  const bundle = await getStock(code);
  if (!bundle) notFound();

  const requested = one(sp.d);
  // 처음 열 때는 최근 '재무 영향이 있는' 공시를 미리 선택해 둔다
  const defaultD =
    bundle.disclosures.find((d) => d.impact && d.notable)?.rcept_no ??
    bundle.disclosures.find((d) => d.impact)?.rcept_no ??
    bundle.disclosures[0]?.rcept_no ??
    null;
  const initial: ViewState = {
    tab: pick<Tab>(one(sp.tab), ["health", "financials", "history", "peers"], "health"),
    d: requested && bundle.disclosures.some((x) => x.rcept_no === requested) ? requested : defaultD,
    range: pick<Range>(one(sp.range), ["3M", "6M", "1Y", "3Y", "ALL"], "1Y"),
    mode: pick<ChartMode>(one(sp.mode), ["price", "relative"], "price"),
    bm: pick<Benchmark>(one(sp.bm), ["ew", "kospi"], "ew"),
  };
  return <StockView bundle={bundle} initial={initial} />;
}
