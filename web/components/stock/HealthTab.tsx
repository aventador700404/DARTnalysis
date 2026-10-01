"use client";

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { AXES, AXIS_METRICS, METRIC_LABELS } from "@/lib/categories";
import { multiple, pct } from "@/lib/format";
import type { Score, Valuation } from "@/lib/types";
import { Empty } from "../ui";

function fmtMetric(key: string, v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "–";
  const f = METRIC_LABELS[key]?.format;
  if (f === "pct") return pct(v, 1, false);
  if (f === "x") return multiple(v);
  if (f === "times") return `${v.toFixed(1)}배`;
  if (f === "pctile") return `${Math.round(v)}% 지점${v <= 30 ? " (싼 편)" : v >= 70 ? " (비싼 편)" : ""}`;
  return String(v);
}

export function HealthTab({ score, valuation, peerGroup, name }: { score: Score | null; valuation: Valuation | null; peerGroup: string | null; name: string }) {
  if (!score || AXES.every((a) => score[a.key] == null)) {
    return <Empty>{score?.note ?? "건강검진 점수를 계산할 데이터가 아직 없어요."}</Empty>;
  }
  const data = AXES.map((a) => ({ axis: a.label, score: score[a.key] ?? 0, mid: 50 }));
  const raw = valuation as unknown as Record<string, number | null> | null;

  return (
    <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 p-4 sm:p-5">
      <div>
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={data} outerRadius="72%" margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
              <PolarGrid stroke="var(--grid)" />
              <PolarAngleAxis dataKey="axis" tick={{ fill: "var(--ink-2)", fontSize: 12, fontWeight: 600 }} />
              <PolarRadiusAxis domain={[0, 100]} tickCount={5} tick={false} axisLine={false} />
              <Radar dataKey="mid" stroke="var(--bench-1)" strokeWidth={1} fill="none" isAnimationActive={false} />
              <Radar dataKey="score" stroke="var(--series-1)" strokeWidth={2} fill="var(--series-1)" fillOpacity={0.12} dot={{ r: 3.5, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-center gap-4 text-[11px] text-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-[2px] bg-[var(--series-1)]" aria-hidden />
            {name}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-[1px] bg-[var(--bench-1)]" aria-hidden />
            업종 중간 (50점)
          </span>
        </div>
        <p className="mt-3 text-xs text-ink-3 leading-relaxed">
          점수는 {peerGroup ? <b className="text-ink-2 font-medium">{peerGroup}</b> : "같은 업종"} 기업들 사이에서의 순위(백분위)예요. 50점이면 딱 중간, 100점이면
          1등. 임의 기준이나 가중치 없이 각 항목을 따로 보여주고, 합쳐서 점수 하나로 만들지 않아요.
        </p>
        {score.note && <p className="mt-2 text-xs text-[var(--critical)]">⚠ {score.note}</p>}
      </div>

      <ul className="divide-y divide-[var(--border)]">
        {AXES.map((a) => {
          const v = score[a.key];
          return (
            <li key={a.key} className="py-3 first:pt-0">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <span className="text-sm font-semibold">{a.label}</span>
                  <span className="text-xs text-ink-3 ml-2">{a.desc}</span>
                </div>
                <span className="text-lg font-bold tracking-[-0.02em] tnum shrink-0">{v == null ? "–" : Math.round(v)}</span>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full bg-surface-3 overflow-hidden" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={v ?? 0} aria-label={`${a.label} 점수`}>
                <div className="h-full rounded-full bg-[var(--series-1)] transition-[width] duration-500" style={{ width: `${v ?? 0}%` }} />
              </div>
              <dl className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-xs">
                {AXIS_METRICS[a.key].map((m) => (
                  <div key={m} className="min-w-0">
                    <dt className="text-ink-3 truncate">{METRIC_LABELS[m].label}</dt>
                    <dd className="tnum text-ink">
                      {fmtMetric(m, raw?.[m])}
                      {score.metric_scores[m] != null && (
                        <span className="text-ink-3 ml-1" title={score.basis[m] === "업종" ? "업종 안 백분위" : "업종 회사 수가 적어 코스피 전체 기준 백분위"}>
                          · {score.basis[m] === "코스피 전체" ? "전체" : "업종"} {Math.round(score.metric_scores[m])}점
                        </span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
