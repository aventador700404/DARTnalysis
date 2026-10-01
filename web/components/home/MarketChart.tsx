"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { shortDate } from "@/lib/format";

export function MarketChart({ dates, kospi, ew }: { dates: string[]; kospi: (number | null)[]; ew: (number | null)[] }) {
  const k0 = kospi.find((v) => v != null) ?? 1;
  const e0 = ew.find((v) => v != null) ?? 1;
  const data = dates.map((d, i) => ({
    d,
    kospi: kospi[i] != null ? ((kospi[i] as number) / k0) * 100 : null,
    ew: ew[i] != null ? ((ew[i] as number) / e0) * 100 : null,
  }));
  const last = data[data.length - 1];
  return (
    <div>
      <div className="h-[150px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 40, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="d" tickFormatter={shortDate} tick={{ fill: "var(--ink-3)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={40} />
            <YAxis tick={{ fill: "var(--ink-3)", fontSize: 10 }} tickLine={false} axisLine={false} width={32} domain={["auto", "auto"]} tickFormatter={(v: number) => v.toFixed(0)} />
            <Tooltip
              cursor={{ stroke: "var(--ink-3)", strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="card px-2.5 py-1.5 text-xs">
                    <div className="text-ink-3 tnum">{String(label).replaceAll("-", ".")}</div>
                    {payload.map((p) => (
                      <div key={String(p.dataKey)} className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-1.5 text-ink-2">
                          <span className="w-2.5 h-[2px]" style={{ background: p.color }} aria-hidden />
                          {p.dataKey === "kospi" ? "코스피" : "동일가중"}
                        </span>
                        <b className="tnum">{Number(p.value).toFixed(1)}</b>
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            <Line dataKey="kospi" stroke="var(--ink)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="ew" stroke="var(--bench-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-4 text-[11px] text-ink-2 mt-1">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-[2px] bg-[var(--ink)]" aria-hidden />
          코스피 <b className="tnum">{last?.kospi?.toFixed(1)}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-[2px] bg-[var(--bench-1)]" aria-hidden />
          코스피 동일가중 <b className="tnum">{last?.ew?.toFixed(1)}</b>
        </span>
        <span className="text-ink-3">1년 전 = 100</span>
      </div>
    </div>
  );
}
