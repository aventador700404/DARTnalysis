"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { krw, pct } from "@/lib/format";
import type { FinancialQuarter } from "@/lib/types";
import { Empty, Segmented } from "../ui";

type Basis = "quarter" | "ttm";

export function FinancialsTab({ financials }: { financials: FinancialQuarter[] }) {
  const [basis, setBasis] = useState<Basis>("quarter");
  const [table, setTable] = useState(false);
  if (!financials.length) return <Empty>재무 데이터가 아직 없어요.</Empty>;

  const rows = financials.slice(-12).map((q) => {
    const rev = basis === "quarter" ? q.revenue : q.ttm_revenue;
    const op = basis === "quarter" ? q.operating_income : q.ttm_operating_income;
    return {
      label: `${String(q.year).slice(2)}.${q.quarter}Q`,
      revenue: rev,
      op,
      margin: rev && op != null ? op / rev : null,
      available: q.available_from,
    };
  });

  return (
    <div className="p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented<Basis>
          label="기준"
          value={basis}
          onChange={setBasis}
          options={[
            { value: "quarter", label: "분기" },
            { value: "ttm", label: "최근 4분기 합" },
          ]}
        />
        <button type="button" onClick={() => setTable((t) => !t)} className="text-xs text-ink-2 hover:text-ink underline-offset-2 hover:underline">
          {table ? "차트로 보기" : "표로 보기"}
        </button>
      </div>

      {table ? (
        <div className="mt-4 overflow-x-auto thin-scroll">
          <table className="w-full text-sm tnum">
            <thead>
              <tr className="text-xs text-ink-3 border-b border-line">
                <th className="text-left font-medium py-2">분기</th>
                <th className="text-right font-medium">매출</th>
                <th className="text-right font-medium">영업이익</th>
                <th className="text-right font-medium">영업이익률</th>
                <th className="text-right font-medium">공시일</th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((r) => (
                <tr key={r.label} className="border-b border-line last:border-0">
                  <td className="py-2">{r.label}</td>
                  <td className="text-right">{krw(r.revenue)}</td>
                  <td className="text-right">{krw(r.op)}</td>
                  <td className="text-right">{pct(r.margin, 1, false)}</td>
                  <td className="text-right text-ink-3">{r.available?.replaceAll("-", ".")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4 grid md:grid-cols-3 gap-5">
          <MiniBars title="매출" data={rows} dataKey="revenue" />
          <MiniBars title="영업이익" data={rows} dataKey="op" />
          <MiniLine title="영업이익률" data={rows} />
        </div>
      )}
      <p className="mt-4 text-[11px] text-ink-3 leading-relaxed">
        분·반기 보고서는 누적 금액으로 나와서, 4분기 = 연간 − 3분기 누적으로 계산했어요. 각 숫자는 보고서가 공시된 날부터 밸류에이션 계산에 쓰여요 (미래 정보 사용 방지).
      </p>
    </div>
  );
}

const axisTick = { fill: "var(--ink-3)", fontSize: 10 };

function ChartTooltip({ active, payload, label, kind }: { active?: boolean; payload?: { value: number }[]; label?: string; kind: "krw" | "pct" }) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  return (
    <div className="card px-2.5 py-1.5 text-xs">
      <div className="font-semibold tnum">{kind === "krw" ? `${krw(v)}원` : pct(v, 1, false)}</div>
      <div className="text-ink-3">{label}</div>
    </div>
  );
}

function MiniBars({ title, data, dataKey }: { title: string; data: Record<string, unknown>[]; dataKey: string }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ink-2 mb-1">{title}</div>
      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="label" tick={axisTick} tickLine={false} axisLine={{ stroke: "var(--axis)" }} interval="preserveStartEnd" minTickGap={14} />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} width={44} tickFormatter={(v: number) => krw(v, 0)} />
            <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip kind="krw" />} />
            <Bar dataKey={dataKey} fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={18} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function MiniLine({ title, data }: { title: string; data: Record<string, unknown>[] }) {
  return (
    <div>
      <div className="text-xs font-semibold text-ink-2 mb-1">{title}</div>
      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="label" tick={axisTick} tickLine={false} axisLine={{ stroke: "var(--axis)" }} interval="preserveStartEnd" minTickGap={14} />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} width={40} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
            <Tooltip cursor={{ stroke: "var(--ink-3)", strokeWidth: 1 }} content={<ChartTooltip kind="pct" />} />
            <Line dataKey="margin" stroke="var(--series-1)" strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
