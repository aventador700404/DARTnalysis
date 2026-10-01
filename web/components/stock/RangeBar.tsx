// 유형별 과거 반응 분포: 10~90% 구간(얇은 막대), 25~75%(굵은 막대), 중앙값(세로선), 이 공시(점)
import { pct } from "@/lib/format";

export function RangeBar({
  p10,
  p25,
  median,
  p75,
  p90,
  value,
  label,
}: {
  p10: number;
  p25: number;
  median: number;
  p75: number;
  p90: number;
  value: number | null;
  label: string;
}) {
  const lo = Math.min(p10, value ?? p10, 0);
  const hi = Math.max(p90, value ?? p90, 0);
  const pad = (hi - lo) * 0.08 || 0.01;
  const min = lo - pad;
  const max = hi + pad;
  const x = (v: number) => ((v - min) / (max - min)) * 100;
  return (
    <div>
      <svg viewBox="0 0 100 18" preserveAspectRatio="none" className="w-full h-[18px] overflow-visible" role="img" aria-label={`${label}: 중앙값 ${pct(median)}, 가운데 50% 범위 ${pct(p25)} ~ ${pct(p75)}${value != null ? `, 이 공시 ${pct(value)}` : ""}`}>
        <line x1={x(0)} x2={x(0)} y1="1" y2="17" stroke="var(--axis)" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />
        <line x1={x(p10)} x2={x(p90)} y1="9" y2="9" stroke="var(--surface-3)" strokeWidth="4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        <line x1={x(p25)} x2={x(p75)} y1="9" y2="9" stroke="var(--bench-1)" strokeWidth="8" strokeLinecap="round" vectorEffect="non-scaling-stroke" opacity="0.55" />
        <line x1={x(median)} x2={x(median)} y1="3" y2="15" stroke="var(--ink)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      {value != null && (
        <div className="relative h-0">
          <span
            className="absolute -top-[13px] w-2.5 h-2.5 -ml-[5px] rounded-full bg-[var(--brand)] ring-2 ring-[var(--surface)]"
            style={{ left: `${x(value)}%` }}
            title={`이 공시 ${pct(value)}`}
          />
        </div>
      )}
      <div className="flex justify-between text-[10px] text-ink-3 tnum mt-1">
        <span>{pct(p10)}</span>
        <span>0%</span>
        <span>{pct(p90)}</span>
      </div>
    </div>
  );
}
