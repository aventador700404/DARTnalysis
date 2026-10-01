"use client";

import { useSyncExternalStore } from "react";

type Mode = "light" | "dark";

function current(): Mode {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribe(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  window.addEventListener("themechange", cb);
  return () => {
    mq.removeEventListener("change", cb);
    window.removeEventListener("themechange", cb);
  };
}

export function ThemeToggle() {
  const mode = useSyncExternalStore<Mode | null>(subscribe, current, () => null);

  const toggle = () => {
    const next: Mode = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {}
    window.dispatchEvent(new Event("themechange")); // 차트가 색을 다시 읽도록
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className="w-9 h-9 grid place-items-center rounded-xl text-ink-2 hover:text-ink hover:bg-surface-2 transition-colors"
      aria-label={mode === "dark" ? "라이트 모드로" : "다크 모드로"}
      title={mode === "dark" ? "라이트 모드로" : "다크 모드로"}
    >
      {mode === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="4.5" fill="currentColor" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <path key={a} d="M12 2.5v2.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" transform={`rotate(${a} 12 12)`} />
          ))}
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
          <path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" fill="currentColor" />
        </svg>
      )}
    </button>
  );
}
