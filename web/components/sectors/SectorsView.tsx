"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { krw, multiple, pct } from "@/lib/format";
import type { SectorData, SectorRow } from "@/lib/types";
import { Card, CardHeader, Delta, Segmented } from "../ui";

type Mode = "theme" | "ksic";
type SortKey = "market_cap" | "per" | "pbr" | "roe" | "op_margin" | "revenue_cagr_3y" | "change1d";

const COLS: { key: SortKey; label: string; fmt: (r: SectorRow) => React.ReactNode }[] = [
  { key: "market_cap", label: "시가총액", fmt: (r) => krw(r.valuation?.market_cap) },
  { key: "per", label: "PER", fmt: (r) => multiple(r.valuation?.per) },
  { key: "pbr", label: "PBR", fmt: (r) => multiple(r.valuation?.pbr, 2) },
  { key: "roe", label: "ROE", fmt: (r) => pct(r.valuation?.roe, 1, false) },
  { key: "op_margin", label: "영업이익률", fmt: (r) => pct(r.valuation?.op_margin, 1, false) },
  { key: "revenue_cagr_3y", label: "매출 3년 성장", fmt: (r) => pct(r.valuation?.revenue_cagr_3y) },
  { key: "change1d", label: "전일 대비", fmt: (r) => <Delta value={r.change1d} /> },
];

const val = (r: SectorRow, k: SortKey) => (k === "change1d" ? r.change1d : (r.valuation?.[k] as number | null | undefined)) ?? null;

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function SectorsView({ data }: { data: SectorData }) {
  const [mode, setMode] = useState<Mode>("theme");
  const groups = useMemo(() => {
    const m = new Map<string, SectorRow[]>();
    for (const r of data.rows) {
      const keys = mode === "theme" ? r.company.themes : [r.company.ksic_name ?? r.company.ksic ?? "기타"];
      for (const k of keys) m.set(k, [...(m.get(k) ?? []), r]);
    }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [data.rows, mode]);
  const [picked, setPicked] = useState<string | null>(null);
  const group = groups.find(([g]) => g === picked) ?? groups[0];
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "market_cap", desc: true });

  if (!group) return null;
  const [name, rows] = group;
  const sorted = [...rows].sort((a, b) => {
    const x = val(a, sort.key);
    const y = val(b, sort.key);
    if (x == null) return 1;
    if (y == null) return -1;
    return sort.desc ? y - x : x - y;
  });
  const totalCap = rows.reduce((s, r) => s + (r.valuation?.market_cap ?? 0), 0);
  const revs = rows.map((r) => r.valuation?.ttm_revenue ?? 0).sort((a, b) => b - a);
  const top3Share = revs.reduce((s, v) => s + v, 0) ? revs.slice(0, 3).reduce((s, v) => s + v, 0) / revs.reduce((s, v) => s + v, 0) : null;
  const medPer = median(rows.map((r) => r.valuation?.per).filter((v): v is number => v != null && v > 0));

  const roePbr = rows.filter((r) => r.valuation?.roe != null && r.valuation?.pbr != null).map((r) => ({ name: r.company.name, x: r.valuation!.roe!, y: r.valuation!.pbr! }));
  const growthMargin = rows
    .filter((r) => r.valuation?.revenue_cagr_3y != null && r.valuation?.op_margin != null)
    .map((r) => ({ name: r.company.name, x: r.valuation!.revenue_cagr_3y!, y: r.valuation!.op_margin! }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-[-0.03em]">업종 비교</h1>
          <p className="text-sm text-ink-3 mt-0.5">같은 업종 기업들의 규모·수익성·가격을 한 번에 비교해요</p>
        </div>
        <Segmented<Mode>
          label="분류 기준"
          value={mode}
          onChange={(m) => {
            setMode(m);
            setPicked(null);
          }}
          options={[
            { value: "theme", label: "투자 테마" },
            { value: "ksic", label: "공식 분류 (KSIC)" },
          ]}
        />
      </div>
      {mode === "ksic" && (
        <p className="text-xs text-ink-3 bg-surface rounded-lg border border-line px-3 py-2 leading-relaxed">
          공식 분류는 통계용이라 회사마다 업종 하나만 붙어요. 그래서 실제 경쟁사가 다른 업종으로 갈리기도 해요 (예: 반도체 대형주가 &lsquo;통신 및 방송 장비 제조업&rsquo;으로
          분류). &lsquo;투자 테마&rsquo;는 이 문제를 보완하려고 직접 설계한 분류예요.
        </p>
      )}

      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="업종 선택">
        {groups.map(([g, rs]) => (
          <button
            key={g}
            type="button"
            role="radio"
            aria-checked={g === name}
            onClick={() => setPicked(g)}
            className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${g === name ? "bg-ink text-surface border-transparent font-semibold" : "border-line text-ink-2 hover:bg-surface hover:text-ink"}`}
          >
            {g} <span className="opacity-60 tnum">{rs.length}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Tile label="기업 수" value={`${rows.length}개`} />
        <Tile label="합산 시가총액" value={`${krw(totalCap)}원`} />
        <Tile label="매출 상위 3개사 점유율" value={pct(top3Share, 0, false)} sub="업종 안 매출 집중도 (최근 4분기)" />
        <Tile label="PER 중앙값" value={multiple(medPer)} sub="적자 기업 제외" />
      </div>

      <Card className="overflow-hidden">
        <CardHeader title={`${name} 기업`} sub="열 제목을 누르면 정렬돼요" />
        <div className="overflow-x-auto thin-scroll mt-2">
          <table className="w-full text-sm tnum min-w-[720px]">
            <thead>
              <tr className="text-xs text-ink-3 border-b border-line">
                <th className="text-left font-medium py-2 pl-4 sm:pl-5">종목</th>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    className="text-right font-medium last:pr-4 sm:last:pr-5"
                    aria-sort={sort.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}
                  >
                    <button
                      type="button"
                      onClick={() => setSort((s) => ({ key: c.key, desc: s.key === c.key ? !s.desc : true }))}
                      className={`hover:text-ink ${sort.key === c.key ? "text-ink font-semibold" : ""}`}
                    >
                      {c.label}
                      {sort.key === c.key ? (sort.desc ? " ↓" : " ↑") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.company.code} className="border-b border-line last:border-0 hover:bg-surface-2">
                  <td className="py-2.5 pl-4 sm:pl-5">
                    <Link href={`/stock/${r.company.code}`} className="font-medium hover:underline">
                      {r.company.name}
                    </Link>
                    <span className="text-xs text-ink-3 ml-1.5">{r.company.code}</span>
                  </td>
                  {COLS.map((c) => (
                    <td key={c.key} className="text-right last:pr-4 sm:last:pr-5">
                      {c.fmt(r)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="pb-4">
          <CardHeader title="ROE × PBR" sub="오른쪽 아래일수록 버는 힘에 비해 싸게 평가받는 편 · 기준선은 중앙값" />
          <Scatter2 points={roePbr} xFmt={(v) => `${Math.round(v * 100)}%`} yFmt={(v) => `${v.toFixed(1)}배`} xLabel="ROE" yLabel="PBR" />
        </Card>
        <Card className="pb-4">
          <CardHeader title="성장성 × 수익성" sub="매출 3년 연평균 성장률 × 영업이익률 · 오른쪽 위일수록 잘 크고 많이 남김" />
          <Scatter2 points={growthMargin} xFmt={(v) => `${Math.round(v * 100)}%`} yFmt={(v) => `${Math.round(v * 100)}%`} xLabel="매출 성장률" yLabel="영업이익률" />
        </Card>
      </div>
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="px-4 py-3" as="div">
      <div className="text-xs text-ink-3">{label}</div>
      <div className="text-xl font-bold tracking-[-0.02em] mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-ink-3 mt-0.5">{sub}</div>}
    </Card>
  );
}

function Scatter2({
  points,
  xFmt,
  yFmt,
  xLabel,
  yLabel,
}: {
  points: { name: string; x: number; y: number }[];
  xFmt: (v: number) => string;
  yFmt: (v: number) => string;
  xLabel: string;
  yLabel: string;
}) {
  const mx = median(points.map((p) => p.x));
  const my = median(points.map((p) => p.y));
  return (
    <div className="h-[260px] px-2 mt-2 relative">
      <span className="absolute left-4 top-0 text-[10px] text-ink-3">↑ {yLabel}</span>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 24, right: 16, bottom: 18, left: 4 }}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis type="number" dataKey="x" tickFormatter={xFmt} tick={{ fill: "var(--ink-3)", fontSize: 10 }} axisLine={{ stroke: "var(--axis)" }} tickLine={false} label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "var(--ink-3)", fontSize: 11 }} />
          <YAxis type="number" dataKey="y" tickFormatter={yFmt} tick={{ fill: "var(--ink-3)", fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
          <ZAxis range={[90, 90]} />
          {mx != null && <ReferenceLine x={mx} stroke="var(--axis)" />}
          {my != null && <ReferenceLine y={my} stroke="var(--axis)" />}
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as { name: string; x: number; y: number };
              return (
                <div className="card px-2.5 py-1.5 text-xs">
                  <div className="font-semibold">{p.name}</div>
                  <div className="text-ink-2 tnum">
                    {xLabel} {xFmt(p.x)} · {yLabel} {yFmt(p.y)}
                  </div>
                </div>
              );
            }}
          />
          <Scatter data={points} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
