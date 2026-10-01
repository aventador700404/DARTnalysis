import type { ReactNode } from "react";
import { CATEGORY_BY_KEY } from "@/lib/categories";
import { arrow, pct, signClass } from "@/lib/format";
import type { CategoryKey } from "@/lib/types";

export function Card({ children, className = "", as: As = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" }) {
  return <As className={`card ${className}`}>{children}</As>;
}

export function CardHeader({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 sm:px-5 pt-4">
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-[-0.02em]">{title}</h2>
        {sub && <p className="text-xs text-ink-3 mt-0.5">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size = "sm",
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  size?: "sm" | "xs";
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex p-0.5 rounded-lg bg-surface-2 border border-line">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`${size === "xs" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs"} rounded-md font-medium transition-colors ${
            o.value === value ? "bg-surface text-ink shadow-[0_1px_2px_rgba(0,0,0,0.08)]" : "text-ink-3 hover:text-ink-2"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function CategoryDot({ category, size = 8 }: { category: CategoryKey; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-block rounded-full shrink-0 ring-2 ring-[var(--surface)]"
      style={{ width: size, height: size, background: CATEGORY_BY_KEY[category]?.color }}
    />
  );
}

export function CategoryTag({ category, label }: { category: CategoryKey; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-ink-2 px-2 py-0.5 rounded-full bg-surface-2 border border-line whitespace-nowrap">
      <CategoryDot category={category} size={7} />
      {label ?? CATEGORY_BY_KEY[category]?.label}
    </span>
  );
}

export function Delta({ value, digits = 1, className = "" }: { value: number | null | undefined; digits?: number; className?: string }) {
  return (
    <span className={`tnum ${signClass(value)} ${className}`}>
      {arrow(value) && <span className="text-[0.7em] mr-0.5 align-[0.1em]">{arrow(value)}</span>}
      {pct(value, digits)}
    </span>
  );
}

export function Stat({ label, value, sub }: { label: ReactNode; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-ink-3">{label}</div>
      <div className="text-lg font-semibold tracking-[-0.02em] mt-0.5 truncate">{value}</div>
      {sub && <div className="text-xs text-ink-3 mt-0.5">{sub}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="text-sm text-ink-3 py-10 text-center">{children}</div>;
}
