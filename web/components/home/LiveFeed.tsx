"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { groupLabel } from "@/lib/categories";
import { date, feedTime, relative } from "@/lib/format";
import type { DataSource, FeedItem } from "@/lib/types";
import { CategoryDot } from "../ui";

interface LiveItem extends FeedItem {
  _key: string;
  _fresh?: boolean;
  _arrivedAt?: string;
}

export function LiveFeed({
  initial,
  demoPool,
  source,
  names,
}: {
  initial: FeedItem[];
  demoPool: FeedItem[];
  source: DataSource;
  names: Record<string, string>;
}) {
  const [items, setItems] = useState<LiveItem[]>(() => initial.map((d) => ({ ...d, _key: d.rcept_no })));
  const [now, setNow] = useState(() => Date.now());
  const poolIdx = useRef(0);

  // 상대 시간 갱신
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  // 실시간: Supabase Realtime (실제) / 데모 재생 (샘플)
  useEffect(() => {
    if (source === "supabase") {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      if (!url || !key) return;
      let cleanup = () => {};
      import("@supabase/supabase-js").then(({ createClient }) => {
        const sb = createClient(url, key);
        const ch = sb
          .channel("disclosures-feed")
          .on("postgres_changes", { event: "INSERT", schema: "public", table: "disclosures" }, (payload) => {
            const d = payload.new as FeedItem;
            const item: LiveItem = {
              ...d,
              company_name: names[d.code] ?? d.code,
              impact: null,
              notable: false,
              base_date: null,
              excluded_reason: null,
              ret_5: null,
              ret_20: null,
              ex_ew_5: null,
              ex_ew_20: null,
              ex_kospi_5: null,
              ex_kospi_20: null,
              _key: d.rcept_no,
              _fresh: true,
              _arrivedAt: new Date().toISOString(),
            };
            setItems((prev) => [item, ...prev.filter((x) => x.rcept_no !== d.rcept_no)].slice(0, 60));
          })
          .subscribe();
        cleanup = () => {
          sb.removeChannel(ch);
        };
      });
      return () => cleanup();
    }
    if (!demoPool.length) return;
    // 데모: 샘플 공시를 30초마다 하나씩 '새로 들어온 것처럼' 다시 보여줌
    const t = setInterval(() => {
      const src = demoPool[poolIdx.current % demoPool.length];
      poolIdx.current += 1;
      const arrived = new Date().toISOString();
      setItems((prev) => [{ ...src, _key: `${src.rcept_no}-${arrived}`, _fresh: true, _arrivedAt: arrived }, ...prev].slice(0, 60));
    }, 30_000);
    return () => clearInterval(t);
  }, [source, demoPool, names]);

  return (
    <ul className="divide-y divide-[var(--border)]" aria-live="polite">
      {items.map((d) => {
        const when = d._arrivedAt ?? d.first_seen_at;
        return (
          <li key={d._key} className={`px-4 sm:px-5 py-3 ${d._fresh ? "animate-slide-in" : ""}`}>
            <Link href={`/stock/${d.code}?d=${d.rcept_no}`} className="group flex gap-3 items-start">
              <div className="w-[64px] shrink-0 text-[11px] text-ink-3 tnum pt-0.5 leading-tight">
                {when ? (now - new Date(when).getTime() < 3600_000 ? relative(when, now) : feedTime(when, now)) : date(d.rcept_dt).slice(5)}
                {d._fresh && <span className="block text-brand-ink font-semibold">NEW</span>}
              </div>
              <CategoryDot category={d.category} size={9} />
              <div className="min-w-0 flex-1 -mt-[3px]">
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="font-semibold text-sm shrink-0 group-hover:underline">{d.company_name}</span>
                  <span className="text-xs text-ink-3 truncate">{groupLabel(d.group_key)}</span>
                </div>
                <p className="text-[13px] text-ink-2 truncate">{d.report_nm}</p>
                {d.impact?.headline && <p className="text-xs text-ink mt-0.5">{d.impact.headline}</p>}
              </div>
              {d.notable && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-brand-soft text-brand-ink shrink-0">주목</span>}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
