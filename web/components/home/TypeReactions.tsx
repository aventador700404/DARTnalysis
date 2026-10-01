"use client";

import { useState } from "react";
import { CATEGORY_BY_KEY } from "@/lib/categories";
import { pct } from "@/lib/format";
import type { Benchmark, StatRow } from "@/lib/types";
import { CategoryDot, Segmented } from "../ui";

// 공시 유형별 평균 반응 (막대 = 평균 초과수익률, 0 기준 좌우)
export function TypeReactions({ stats }: { stats: StatRow[] }) {
  const [h, setH] = useState<5 | 20>(5);
  const [bm, setBm] = useState<Benchmark>("ew");
  const rows = stats
    .filter((s) => s.horizon === h && s.benchmark === bm && !s.hidden && s.mean != null)
    .sort((a, b) => (b.mean ?? 0) - (a.mean ?? 0));
  const hiddenRows = stats.filter((s) => s.horizon === h && s.benchmark === bm && s.hidden);
  const maxAbs = Math.max(0.01, ...rows.map((r) => Math.abs(r.mean ?? 0)));

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <Segmented<"5" | "20">
          label="기간"
          size="xs"
          value={String(h) as "5" | "20"}
          onChange={(v) => setH(Number(v) as 5 | 20)}
          options={[
            { value: "5", label: "5거래일" },
            { value: "20", label: "20거래일" },
          ]}
        />
        <Segmented<Benchmark>
          label="비교 기준"
          size="xs"
          value={bm}
          onChange={setBm}
          options={[
            { value: "ew", label: "동일가중" },
            { value: "kospi", label: "코스피" },
          ]}
        />
      </div>
      <ul className="mt-3 space-y-2">
        {rows.map((r) => {
          const w = (Math.abs(r.mean!) / maxAbs) * 50;
          const pos = r.mean! >= 0;
          return (
            <li key={r.group_key} className="grid grid-cols-[minmax(0,140px)_minmax(0,1fr)_64px] items-center gap-2 text-xs" title={`중앙값 ${pct(r.median)} · 오른 비율 ${pct(r.up_ratio, 0, false)} · ${r.n}건`}>
              <span className="flex items-center gap-1.5 min-w-0">
                <CategoryDot category={r.category ?? CATEGORY_BY_KEY.other.key} size={7} />
                <span className="truncate text-ink-2">{r.group_label}</span>
              </span>
              <span className="relative h-3.5">
                <span className="absolute top-0 bottom-0 left-1/2 w-px bg-[var(--axis)]" aria-hidden />
                <span
                  className="absolute top-[3px] h-2 rounded-[3px]"
                  style={{
                    left: pos ? "50%" : `${50 - w}%`,
                    width: `${Math.max(w, 0.8)}%`,
                    background: pos ? "var(--up)" : "var(--down)",
                    opacity: 0.85,
                  }}
                  aria-hidden
                />
              </span>
              <span className={`text-right tnum font-semibold ${pos ? "text-up" : "text-down"}`}>
                {pct(r.mean)}
                <span className="block text-[10px] font-normal text-ink-3">{r.n}건</span>
              </span>
            </li>
          );
        })}
      </ul>
      {hiddenRows.length > 0 && (
        <p className="mt-3 text-[11px] text-ink-3">표본 5건 미만이라 숨김: {hiddenRows.map((r) => `${r.group_label}(${r.n})`).join(", ")}</p>
      )}
      <p className="mt-1 text-[11px] text-ink-3">공시 후 시장 대비 평균 초과수익률 (상·하위 1% 제외). 막대에 마우스를 올리면 중앙값과 오른 비율을 볼 수 있어요.</p>
    </div>
  );
}
