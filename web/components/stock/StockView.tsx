"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AXES, CATEGORIES } from "@/lib/categories";
import { date, krw, multiple, pct, price } from "@/lib/format";
import type { Benchmark, CategoryKey, StockBundle } from "@/lib/types";
import { Card, CategoryDot, Delta, Segmented } from "../ui";
import { DisclosurePanel } from "./DisclosurePanel";
import { FinancialsTab } from "./FinancialsTab";
import { HealthTab } from "./HealthTab";
import { HistoryTab } from "./HistoryTab";
import { PeersTab } from "./PeersTab";
import { PriceChart, type ChartMode, type Range } from "./PriceChart";

export type Tab = "health" | "financials" | "history" | "peers";
export interface ViewState {
  tab: Tab;
  d: string | null;
  range: Range;
  mode: ChartMode;
  bm: Benchmark;
}

const TABS: { key: Tab; label: string }[] = [
  { key: "health", label: "건강검진" },
  { key: "financials", label: "재무 추이" },
  { key: "history", label: "공시 이력" },
  { key: "peers", label: "동종업계 비교" },
];

export function StockView({ bundle, initial }: { bundle: StockBundle; initial: ViewState }) {
  const { company, quote, valuation, score, series, disclosures, meta } = bundle;
  const [state, setState] = useState<ViewState>(initial);
  const [enabled, setEnabled] = useState<Set<CategoryKey>>(() => new Set(CATEGORIES.map((c) => c.key)));

  // 화면 상태를 URL에 저장 → 링크 하나로 같은 화면 공유
  useEffect(() => {
    const p = new URLSearchParams();
    if (state.tab !== "health") p.set("tab", state.tab);
    if (state.d) p.set("d", state.d);
    if (state.range !== "1Y") p.set("range", state.range);
    if (state.mode !== "price") p.set("mode", state.mode);
    if (state.bm !== "ew") p.set("bm", state.bm);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [state]);

  const set = useCallback(<K extends keyof ViewState>(k: K, v: ViewState[K]) => setState((s) => ({ ...s, [k]: v })), []);
  const select = useCallback((id: string) => setState((s) => ({ ...s, d: id })), []);

  const visible = useMemo(() => disclosures.filter((d) => enabled.has(d.category)), [disclosures, enabled]);
  const counts = useMemo(() => {
    const m = new Map<CategoryKey, number>();
    for (const d of disclosures) m.set(d.category, (m.get(d.category) ?? 0) + 1);
    return m;
  }, [disclosures]);

  const selectedIdx = visible.findIndex((d) => d.rcept_no === state.d);
  const selected = selectedIdx >= 0 ? visible[selectedIdx] : null;

  const toggleCat = (k: CategoryKey) =>
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  return (
    <div className="space-y-4">
      {/* ── 헤더 ── */}
      <Card className="px-4 sm:px-5 py-4">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap text-xs text-ink-3">
              <span className="tnum">{company.code}</span>
              <span aria-hidden>·</span>
              <span>{company.market}</span>
              {company.ksic_name && (
                <>
                  <span aria-hidden>·</span>
                  <span title={`공식 업종코드 ${company.ksic}`}>{company.ksic_name}</span>
                </>
              )}
              {company.themes.map((t) => (
                <span key={t} className="px-2 py-0.5 rounded-full bg-surface-2 border border-line text-ink-2">
                  {t}
                </span>
              ))}
            </div>
            <h1 className="text-2xl sm:text-[28px] font-bold tracking-[-0.03em] mt-1">{company.name}</h1>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 mt-1">
              <span className="text-2xl font-bold tracking-[-0.02em] whitespace-nowrap">{price(quote.close)}원</span>
              <Delta value={quote.change1d} digits={2} className="text-base font-semibold" />
              <span className="text-xs text-ink-3">{date(meta.asOf)} 종가 · 하루 지연</span>
            </div>
          </div>
          <dl className="grid grid-cols-3 sm:grid-cols-5 gap-x-5 gap-y-2 text-sm">
            <HeadStat k="시가총액" v={`${krw(valuation?.market_cap)}원`} />
            <HeadStat k="PER" v={valuation?.per != null ? multiple(valuation.per) : "적자"} />
            <HeadStat k="PBR" v={multiple(valuation?.pbr, 2)} />
            <HeadStat k="ROE" v={pct(valuation?.roe, 1, false)} />
            <HeadStat k="배당수익률" v={pct(valuation?.dividend_yield, 1, false)} />
          </dl>
        </div>
        {score && AXES.some((a) => score[a.key] != null) && (
          <div className="mt-3 pt-3 border-t border-line flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-ink-3 mr-1">건강검진</span>
            {AXES.map((a) => (
              <button
                key={a.key}
                type="button"
                onClick={() => {
                  set("tab", "health");
                  document.getElementById("stock-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
                className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg bg-surface-2 hover:bg-surface-3 transition-colors"
              >
                <span className="text-ink-2">{a.label}</span>
                <span className="font-semibold tnum">{score[a.key] == null ? "–" : Math.round(score[a.key]!)}</span>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* ── 차트 + 공시 패널 ── */}
      <Card className="overflow-hidden">
        <div className="px-4 sm:px-5 pt-4 flex flex-wrap items-center gap-2">
          <Segmented<Range>
            label="기간"
            value={state.range}
            onChange={(v) => set("range", v)}
            options={(["3M", "6M", "1Y", "3Y", "ALL"] as Range[]).map((r) => ({ value: r, label: { "3M": "3개월", "6M": "6개월", "1Y": "1년", "3Y": "3년", ALL: "전체" }[r] }))}
          />
          <Segmented<ChartMode>
            label="차트"
            value={state.mode}
            onChange={(v) => set("mode", v)}
            options={[
              { value: "price", label: "주가" },
              { value: "relative", label: "시장 대비" },
            ]}
          />
          <Segmented<Benchmark>
            label="비교 기준"
            value={state.bm}
            onChange={(v) => set("bm", v)}
            options={[
              { value: "ew", label: "동일가중" },
              { value: "kospi", label: "코스피" },
            ]}
          />
          <span className="text-[11px] text-ink-3 hidden xl:inline" title="코스피 지수는 삼성전자·SK하이닉스 같은 대형주 비중이 커서, 모든 종목을 같은 비중으로 평균 낸 지수를 기본 비교 기준으로 써요.">
            비교 기준이 왜 동일가중? ⓘ
          </span>
        </div>
        <div className="px-4 sm:px-5 pt-3 flex flex-wrap gap-1.5" aria-label="차트에 표시할 공시 유형">
          {CATEGORIES.filter((c) => counts.get(c.key)).map((c) => {
            const on = enabled.has(c.key);
            return (
              <button
                key={c.key}
                type="button"
                aria-pressed={on}
                onClick={() => toggleCat(c.key)}
                className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors ${on ? "border-line-strong text-ink" : "border-line text-ink-3 opacity-60"}`}
              >
                <CategoryDot category={c.key} size={8} />
                {c.label}
                <span className="text-ink-3 tnum">{counts.get(c.key)}</span>
              </button>
            );
          })}
        </div>

        <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] mt-2">
          <div className="px-1 sm:px-2 pb-2 min-w-0">
            {state.mode === "relative" && (
              <div className="flex flex-wrap gap-4 px-3 pt-1 text-[11px] text-ink-2">
                <LegendLine color="var(--ink)" label={company.name} />
                <LegendLine color="var(--bench-1)" label="코스피 동일가중" />
                <LegendLine color="var(--bench-2)" label="코스피" />
                <span className="text-ink-3">기간 시작 = 100</span>
              </div>
            )}
            <PriceChart
              dates={series.dates}
              close={series.close}
              kospi={series.kospi}
              ew={series.ew}
              disclosures={visible}
              selected={state.d}
              onSelect={select}
              mode={state.mode}
              range={state.range}
              name={company.name}
            />
          </div>
          <aside className="border-t lg:border-t-0 lg:border-l border-line min-h-[420px] lg:h-[470px]" aria-label="선택한 공시 상세">
            <DisclosurePanel
              d={selected}
              stats={bundle.stats}
              benchmark={state.bm}
              news={bundle.news}
              demo={meta.demo}
              position={selected ? `${selectedIdx + 1}/${visible.length}` : ""}
              onPrev={selected && selectedIdx < visible.length - 1 ? () => select(visible[selectedIdx + 1].rcept_no) : null}
              onNext={selected && selectedIdx > 0 ? () => select(visible[selectedIdx - 1].rcept_no) : null}
            />
          </aside>
        </div>
      </Card>

      {/* ── 하단 탭 ── */}
      <Card className="overflow-hidden scroll-mt-20" as="section">
        <div id="stock-tabs" role="tablist" aria-label="종목 정보" className="flex gap-1 px-3 sm:px-4 pt-2 border-b border-line overflow-x-auto thin-scroll">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              type="button"
              aria-selected={state.tab === t.key}
              onClick={() => set("tab", t.key)}
              className={`relative px-3 py-2.5 text-sm whitespace-nowrap transition-colors ${state.tab === t.key ? "text-ink font-semibold" : "text-ink-3 hover:text-ink-2"}`}
            >
              {t.label}
              {state.tab === t.key && <span className="absolute left-2 right-2 -bottom-px h-[2px] rounded-full bg-[var(--brand)]" aria-hidden />}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="animate-fade-up" key={state.tab}>
          {state.tab === "health" && <HealthTab score={score} valuation={valuation} peerGroup={bundle.peerGroup} name={company.name} />}
          {state.tab === "financials" && <FinancialsTab financials={bundle.financials} />}
          {state.tab === "history" && (
            <HistoryTab
              disclosures={disclosures}
              benchmark={state.bm}
              selected={state.d}
              onSelect={(id) => {
                setEnabled(new Set(CATEGORIES.map((c) => c.key)));
                select(id);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          )}
          {state.tab === "peers" && <PeersTab peers={bundle.peers} group={bundle.peerGroup} />}
        </div>
      </Card>
    </div>
  );
}

function HeadStat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-3">{k}</dt>
      <dd className="font-semibold tnum mt-0.5">{v}</dd>
    </div>
  );
}

function LegendLine({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="w-3 h-[2px] rounded" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}
