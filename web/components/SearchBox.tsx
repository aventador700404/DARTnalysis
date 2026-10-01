"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

export function SearchBox({ companies }: { companies: { code: string; name: string }[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return companies
      .filter((c) => c.name.toLowerCase().includes(s) || c.code.toLowerCase().includes(s))
      .sort((a, b) => Number(!a.name.toLowerCase().startsWith(s)) - Number(!b.name.toLowerCase().startsWith(s)))
      .slice(0, 8);
  }, [q, companies]);

  // "/" 키로 검색창 열기
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (code: string) => {
    setQ("");
    setOpen(false);
    inputRef.current?.blur();
    router.push(`/stock/${code}`);
  };

  return (
    <div className="relative">
      <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none" width="16" height="16" viewBox="0 0 24 24" aria-hidden>
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" fill="none" />
        <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && results[active]) {
            go(results[active].code);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        placeholder="종목명 또는 코드 검색"
        className="w-full h-9 pl-9 pr-9 rounded-xl bg-surface-2 border border-transparent focus:border-line-strong focus:bg-surface outline-none text-sm placeholder:text-ink-3 transition-colors"
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
      />
      <kbd className="hidden sm:block absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] text-ink-3 border border-line rounded px-1.5 leading-4">/</kbd>
      {open && results.length > 0 && (
        <ul id={listId} role="listbox" className="absolute z-40 mt-1.5 w-full card py-1 overflow-hidden animate-fade-up">
          {results.map((c, i) => (
            <li key={c.code} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(c.code)}
                onMouseEnter={() => setActive(i)}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm text-left ${i === active ? "bg-surface-2" : ""}`}
              >
                <span className="font-medium">{c.name}</span>
                <span className="text-xs text-ink-3 tnum">{c.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
