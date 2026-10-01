"use client";

import Link from "next/link";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { krw, multiple, pct } from "@/lib/format";
import type { PeerRow } from "@/lib/types";
import { Delta, Empty } from "../ui";

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function PeersTab({ peers, group }: { peers: PeerRow[]; group: string | null }) {
  if (peers.length <= 1) return <Empty>같은 테마로 묶인 비교 대상이 아직 없어요.</Empty>;
  const sorted = [...peers].sort((a, b) => (b.valuation?.market_cap ?? 0) - (a.valuation?.market_cap ?? 0));
  const pts = peers
    .filter((p) => p.valuation?.roe != null && p.valuation?.pbr != null)
    .map((p) => ({ name: p.company.name, roe: p.valuation!.roe!, pbr: p.valuation!.pbr!, self: p.isSelf }));
  const mRoe = median(pts.map((p) => p.roe));
  const mPbr = median(pts.map((p) => p.pbr));

  return (
    <div className="p-4 sm:p-5 grid lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] gap-6">
      <div className="overflow-x-auto thin-scroll -mx-4 sm:mx-0">
        <table className="w-full text-sm tnum min-w-[560px]">
          <thead>
            <tr className="text-xs text-ink-3 border-b border-line">
              <th className="text-left font-medium py-2 pl-4 sm:pl-0">{group} 종목</th>
              <th className="text-right font-medium">시가총액</th>
              <th className="text-right font-medium">PER</th>
              <th className="text-right font-medium">PBR</th>
              <th className="text-right font-medium">ROE</th>
              <th className="text-right font-medium">영업이익률</th>
              <th className="text-right font-medium pr-4 sm:pr-0">전일 대비</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.company.code} className={`border-b border-line last:border-0 ${p.isSelf ? "bg-brand-soft" : ""}`}>
                <td className="py-2.5 pl-4 sm:pl-0">
                  {p.isSelf ? (
                    <span className="font-semibold">{p.company.name}</span>
                  ) : (
                    <Link href={`/stock/${p.company.code}`} className="hover:underline">
                      {p.company.name}
                    </Link>
                  )}
                </td>
                <td className="text-right">{krw(p.valuation?.market_cap)}</td>
                <td className="text-right">{multiple(p.valuation?.per)}</td>
                <td className="text-right">{multiple(p.valuation?.pbr, 2)}</td>
                <td className="text-right">{pct(p.valuation?.roe, 1, false)}</td>
                <td className="text-right">{pct(p.valuation?.op_margin, 1, false)}</td>
                <td className="text-right pr-4 sm:pr-0">
                  <Delta value={p.change1d} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <div className="text-xs font-semibold text-ink-2">ROE × PBR</div>
        <p className="text-[11px] text-ink-3 mt-0.5">오른쪽 아래(ROE는 높은데 PBR은 낮은 쪽)일수록 돈 버는 힘에 비해 싸게 평가받는 편이에요. 기준선은 그룹 중앙값.</p>
        <div className="h-[260px] mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 12, bottom: 18, left: 0 }}>
              <CartesianGrid stroke="var(--grid)" />
              <XAxis type="number" dataKey="roe" name="ROE" tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={{ fill: "var(--ink-3)", fontSize: 10 }} axisLine={{ stroke: "var(--axis)" }} tickLine={false} label={{ value: "ROE", position: "insideBottom", offset: -10, fill: "var(--ink-3)", fontSize: 11 }} />
              <YAxis type="number" dataKey="pbr" name="PBR" tickFormatter={(v: number) => `${v.toFixed(1)}배`} tick={{ fill: "var(--ink-3)", fontSize: 10 }} axisLine={false} tickLine={false} width={42} />
              <ZAxis range={[90, 90]} />
              {mRoe != null && <ReferenceLine x={mRoe} stroke="var(--axis)" />}
              {mPbr != null && <ReferenceLine y={mPbr} stroke="var(--axis)" />}
              <Tooltip
                cursor={false}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload as (typeof pts)[number];
                  return (
                    <div className="card px-2.5 py-1.5 text-xs">
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-ink-2 tnum">
                        ROE {pct(p.roe, 1, false)} · PBR {multiple(p.pbr, 2)}
                      </div>
                    </div>
                  );
                }}
              />
              <Scatter data={pts.filter((p) => !p.self)} fill="var(--bench-1)" stroke="var(--surface)" strokeWidth={2} />
              <Scatter data={pts.filter((p) => p.self)} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-ink-2 mt-1">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--series-1)]" aria-hidden />이 종목
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--bench-1)]" aria-hidden />
            같은 테마
          </span>
        </div>
      </div>
    </div>
  );
}
