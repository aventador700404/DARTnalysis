import Link from "next/link";
import { krw, pct } from "@/lib/format";
import type { Quote } from "@/lib/types";

// 등락률 → 색 (상승 빨강 / 하락 파랑, 0 근처는 회색). ±3%에서 가장 진함.
// 글자는 배경이 충분히 진할 때(80% 이상)만 흰색 → 명암비 4.5:1 이상 유지
function tone(x: number | null): { bg: string; ink: string } {
  if (x == null || Math.abs(x) < 0.001) return { bg: "var(--surface-2)", ink: "var(--ink-2)" };
  const t = Math.min(1, Math.abs(x) / 0.03);
  const base = x > 0 ? "var(--up)" : "var(--down)";
  const mix = Math.round(12 + t * 80);
  return { bg: `color-mix(in oklab, ${base} ${mix}%, var(--surface))`, ink: mix >= 80 ? "#ffffff" : "var(--ink)" };
}

export function ThemeHeatmap({ themes }: { themes: { theme: string; members: Quote[] }[] }) {
  return (
    <div className="grid sm:grid-cols-2 gap-x-5 gap-y-4">
      {themes.map(({ theme, members }) => (
        <div key={theme}>
          <div className="text-xs font-semibold text-ink-2 mb-1.5">{theme}</div>
          <div className="grid grid-cols-3 gap-[2px] rounded-lg overflow-hidden">
            {members.map((q) => {
              const c = tone(q.change1d);
              return (
                <Link
                  key={q.company.code}
                  href={`/stock/${q.company.code}`}
                  className="px-2 py-2 min-h-[52px] flex flex-col justify-between hover:brightness-[0.97] transition"
                  style={{ background: c.bg, color: c.ink }}
                  title={`${q.company.name} · 시가총액 ${krw(q.marketCap)}원`}
                >
                  <span className="text-xs font-medium truncate">{q.company.name}</span>
                  <span className="text-xs font-semibold tnum">{pct(q.change1d, 2)}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
