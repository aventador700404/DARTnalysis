"use client";

import { useEffect, useState } from "react";

// 캔버스 차트는 CSS 변수를 직접 못 읽어서, 실제 색 값으로 풀어서 넘겨준다.
const NAMES = [
  "surface",
  "surface-2",
  "ink",
  "ink-2",
  "ink-3",
  "grid",
  "axis",
  "brand",
  "up",
  "down",
  "bench-1",
  "bench-2",
  "series-1",
  "series-2",
  "cat-earnings",
  "cat-financing",
  "cat-buyback",
  "cat-ownership",
  "cat-other",
] as const;

export type ThemeColors = Record<(typeof NAMES)[number], string> & { dark: boolean };

function read(): ThemeColors {
  const cs = getComputedStyle(document.documentElement);
  const out = Object.fromEntries(NAMES.map((n) => [n, cs.getPropertyValue(`--${n}`).trim()])) as unknown as ThemeColors;
  out.dark = cs.colorScheme === "dark";
  return out;
}

export function useThemeColors(): ThemeColors | null {
  const [colors, setColors] = useState<ThemeColors | null>(null);
  useEffect(() => {
    const update = () => setColors(read());
    update();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    window.addEventListener("themechange", update);
    return () => {
      mq.removeEventListener("change", update);
      window.removeEventListener("themechange", update);
    };
  }, []);
  return colors;
}

/** "#rrggbb" + 투명도 → rgba() (차트 영역 채우기용) */
export function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  if (h.length !== 6) return hex;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
