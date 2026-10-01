"use client";

import { useMemo, useState } from "react";
import { CATEGORIES, groupLabel } from "@/lib/categories";
import { date } from "@/lib/format";
import type { Benchmark, CategoryKey, Disclosure } from "@/lib/types";
import { CategoryDot, Delta, Empty } from "../ui";

export function HistoryTab({
  disclosures,
  benchmark,
  selected,
  onSelect,
}: {
  disclosures: Disclosure[];
  benchmark: Benchmark;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [cat, setCat] = useState<CategoryKey | "all">("all");
  const [limit, setLimit] = useState(20);
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of disclosures) m.set(d.category, (m.get(d.category) ?? 0) + 1);
    return m;
  }, [disclosures]);
  const all = cat === "all" ? disclosures : disclosures.filter((d) => d.category === cat);
  const rows = all.slice(0, limit);
  const pick = (c: CategoryKey | "all") => {
    setCat(c);
    setLimit(20);
  };

  return (
    <div className="p-4 sm:p-5">
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="공시 유형 필터">
        <FilterChip active={cat === "all"} onClick={() => pick("all")}>
          전체 {disclosures.length}
        </FilterChip>
        {CATEGORIES.filter((c) => counts.get(c.key)).map((c) => (
          <FilterChip key={c.key} active={cat === c.key} onClick={() => pick(c.key)}>
            <CategoryDot category={c.key} size={7} />
            {c.label} {counts.get(c.key)}
          </FilterChip>
        ))}
      </div>
      {rows.length === 0 ? (
        <Empty>공시가 없어요.</Empty>
      ) : (
        <div className="mt-3 overflow-x-auto thin-scroll -mx-4 sm:mx-0">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="text-xs text-ink-3 border-b border-line">
                <th className="text-left font-medium py-2 pl-4 sm:pl-0 w-[92px]">날짜</th>
                <th className="text-left font-medium w-[150px]">유형</th>
                <th className="text-left font-medium">공시명 · 재무 영향</th>
                <th className="text-right font-medium w-[72px]">5일</th>
                <th className="text-right font-medium w-[72px] pr-4 sm:pr-0">20일</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr
                  key={d.rcept_no}
                  onClick={() => onSelect(d.rcept_no)}
                  className={`border-b border-line last:border-0 cursor-pointer transition-colors ${d.rcept_no === selected ? "bg-brand-soft" : "hover:bg-surface-2"}`}
                >
                  <td className="py-2.5 pl-4 sm:pl-0 tnum text-ink-2 align-top">{date(d.base_date ?? d.rcept_dt)}</td>
                  <td className="align-top py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                      <CategoryDot category={d.category} size={7} />
                      {groupLabel(d.group_key)}
                    </span>
                  </td>
                  <td className="py-2.5 align-top">
                    <button type="button" className="text-left" onClick={() => onSelect(d.rcept_no)}>
                      <span className="line-clamp-1 break-all">{d.report_nm}</span>
                      {d.impact?.headline && <span className="block text-xs text-ink-3 mt-0.5">{d.impact.headline}</span>}
                    </button>
                  </td>
                  <td className="text-right align-top py-2.5">
                    <Delta value={d[`ex_${benchmark}_5`]} />
                  </td>
                  <td className="text-right align-top py-2.5 pr-4 sm:pr-0">
                    <Delta value={d[`ex_${benchmark}_20`]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {all.length > rows.length && (
        <button type="button" onClick={() => setLimit((l) => l + 30)} className="mt-3 w-full py-2 text-xs font-medium text-ink-2 rounded-lg border border-line hover:bg-surface-2">
          더 보기 ({all.length - rows.length}건 남음)
        </button>
      )}
      <p className="mt-3 text-[11px] text-ink-3">수익률은 기준일 전날 종가 대비, 같은 기간 {benchmark === "ew" ? "코스피 동일가중 평균" : "코스피 지수"}을 뺀 초과수익률이에요.</p>
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors tnum ${
        active ? "bg-ink text-surface border-transparent" : "border-line text-ink-2 hover:bg-surface-2"
      }`}
    >
      {children}
    </button>
  );
}
