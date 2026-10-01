import Link from "next/link";
import { LiveFeed } from "@/components/home/LiveFeed";
import { MarketChart } from "@/components/home/MarketChart";
import { ThemeHeatmap } from "@/components/home/ThemeHeatmap";
import { TypeReactions } from "@/components/home/TypeReactions";
import { Card, CardHeader, CategoryDot, Delta } from "@/components/ui";
import { groupLabel } from "@/lib/categories";
import { getDemoLivePool, getHome, listCompanies } from "@/lib/data";
import { date } from "@/lib/format";
import { SITE_TAGLINE } from "@/lib/site";

export const revalidate = 60;

export default async function Home() {
  const [home, pool, companies] = await Promise.all([getHome(), getDemoLivePool(), listCompanies()]);
  const names = Object.fromEntries(companies.map((c) => [c.code, c.name]));
  const { meta } = home;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.03em]">지금 코스피에 올라오는 공시</h1>
          <p className="text-sm text-ink-3 mt-0.5">{SITE_TAGLINE} · 공시를 누르면 그 종목 차트에서 바로 열려요</p>
        </div>
        <p className="text-xs text-ink-3">
          데이터 기준 {date(meta.asOf)}
          {meta.demo && " · 가상 기업 샘플"}
        </p>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] gap-4 items-start">
        <Card className="overflow-hidden">
          <CardHeader
            title={
              <span className="flex items-center gap-2">
                실시간 공시
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-ink">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand live-dot" aria-hidden />
                  {meta.demo ? "데모" : "1분마다 확인"}
                </span>
              </span>
            }
            sub={meta.demo ? "샘플 모드에서는 30초마다 과거 샘플 공시를 새로 들어온 것처럼 다시 보여줘요" : "DART에 새 공시가 올라오면 1분 안에 여기에 나타나요"}
          />
          <div className="mt-2 max-h-[720px] overflow-y-auto thin-scroll">
            <LiveFeed initial={home.feed} demoPool={pool} source={meta.source} names={names} />
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="주목할 공시" sub="주식 수·지분이 크게 바뀌는 공시 (최근 120일)" />
            <ul className="mt-2 pb-2">
              {home.notable.length === 0 && <li className="px-5 py-4 text-sm text-ink-3">최근 주목할 공시가 없어요.</li>}
              {home.notable.map((d) => (
                <li key={d.rcept_no}>
                  <Link href={`/stock/${d.code}?d=${d.rcept_no}`} className="flex items-start gap-3 px-4 sm:px-5 py-2.5 hover:bg-surface-2 transition-colors">
                    <CategoryDot category={d.category} size={9} />
                    <div className="min-w-0 flex-1 -mt-[3px]">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm font-semibold">{d.company_name}</span>
                        <span className="text-xs text-ink-3">{groupLabel(d.group_key)}</span>
                        <span className="text-[11px] text-ink-3 tnum ml-auto">{date(d.rcept_dt).slice(5)}</span>
                      </div>
                      <p className="text-xs text-ink-2 mt-0.5">{d.impact?.headline}</p>
                    </div>
                    <div className="text-right text-xs shrink-0 w-14">
                      <Delta value={d.ex_ew_5} />
                      <span className="block text-[10px] text-ink-3">5일 초과</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          <Card className="pb-4">
            <CardHeader title="시장" sub="코스피 지수 vs 전 종목 동일가중 평균 (대형주 쏠림 비교)" />
            <div className="px-4 sm:px-5 mt-3">
              <MarketChart dates={home.market.dates} kospi={home.market.kospi} ew={home.market.ew} />
            </div>
          </Card>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4 items-start">
        <Card className="pb-5">
          <CardHeader title="공시 유형별 평균 반응" sub="과거 코스피 공시 뒤 주가가 시장보다 얼마나 움직였나" />
          <div className="px-4 sm:px-5 mt-3">
            <TypeReactions stats={home.stats} />
          </div>
        </Card>
        <Card className="pb-5">
          <CardHeader title="테마별 등락" sub="전일 대비 · 빨강 상승 / 파랑 하락" right={<Link href="/sectors" className="text-xs text-brand-ink hover:underline shrink-0">업종 비교 →</Link>} />
          <div className="px-4 sm:px-5 mt-3">
            <ThemeHeatmap themes={home.themes} />
          </div>
        </Card>
      </div>
    </div>
  );
}
