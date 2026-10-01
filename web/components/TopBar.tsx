"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SearchBox } from "./SearchBox";
import { ThemeToggle } from "./ThemeToggle";
import { SITE_NAME } from "@/lib/site";

const NAV = [
  { href: "/", label: "홈" },
  { href: "/sectors", label: "업종 비교" },
];

export function TopBar({ companies, demo }: { companies: { code: string; name: string }[]; demo: boolean }) {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-[color-mix(in_oklab,var(--surface)_88%,transparent)] backdrop-blur">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 h-14 flex items-center gap-3 sm:gap-6">
        <Link href="/" className="flex items-center gap-2 shrink-0" aria-label={`${SITE_NAME} 홈`}>
          <Logo />
          <span className="font-bold text-[17px] tracking-[-0.03em] hidden sm:inline">{SITE_NAME}</span>
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`px-3 py-1.5 rounded-lg transition-colors ${active ? "text-ink font-semibold bg-surface-2" : "text-ink-2 hover:text-ink hover:bg-surface-2"}`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex-1 min-w-0 max-w-md">
          <SearchBox companies={companies} />
        </div>
        <div className="flex items-center gap-2 ml-auto">
          {demo ? (
            <span
              className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-surface-2 text-ink-2 border border-line"
              title="가상 기업·가상 공시로 만든 샘플 데이터입니다. 실제 데이터는 Supabase 연결 후 표시됩니다."
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--warn)]" aria-hidden />
              샘플 데이터
            </span>
          ) : (
            <span className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-brand-soft text-brand-ink">
              <span className="w-1.5 h-1.5 rounded-full bg-brand live-dot" aria-hidden />
              LIVE
            </span>
          )}
          <ThemeToggle />
        </div>
      </div>
      <nav className="md:hidden flex border-t border-line text-sm">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className={`flex-1 text-center py-2 ${active ? "text-ink font-semibold" : "text-ink-2"}`}>
              {n.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function Logo() {
  // 차트 선 위에 공시 마커 하나
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
      <rect width="26" height="26" rx="7" fill="var(--brand)" />
      <path d="M5 17.5l4.2-4.4 3.3 2.6L17 9.5l4 3" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="17" cy="9.5" r="2.6" fill="#fff" />
    </svg>
  );
}
