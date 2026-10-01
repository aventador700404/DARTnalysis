"use client";

import {
  AreaSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORY_BY_KEY, groupLabel } from "@/lib/categories";
import { price as fmtPrice } from "@/lib/format";
import type { Disclosure } from "@/lib/types";
import { useThemeColors, withAlpha, type ThemeColors } from "@/lib/useThemeColors";

export type Range = "3M" | "6M" | "1Y" | "3Y" | "ALL";
export type ChartMode = "price" | "relative";

interface Props {
  dates: string[];
  close: (number | null)[];
  kospi: (number | null)[];
  ew: (number | null)[];
  disclosures: Disclosure[];
  selected: string | null;
  onSelect: (rceptNo: string) => void;
  mode: ChartMode;
  range: Range;
  name: string;
}

interface Hover {
  x: number;
  y: number;
  w: number;
  date: string;
  values: { label: string; value: string; color: string }[];
  items: Disclosure[];
}

const MONTHS: Record<Range, number | null> = { "3M": 3, "6M": 6, "1Y": 12, "3Y": 36, ALL: null };

function rangeStart(dates: string[], range: Range): number {
  const months = MONTHS[range];
  if (!months || dates.length === 0) return 0;
  const last = new Date(`${dates[dates.length - 1]}T00:00:00Z`);
  last.setUTCMonth(last.getUTCMonth() - months);
  const cut = last.toISOString().slice(0, 10);
  const i = dates.findIndex((d) => d >= cut);
  return Math.max(0, i);
}

/** 공시가 차트에 찍힐 날짜 = 기준일(없으면 접수일 이후 첫 거래일) */
function markerDate(d: Disclosure, dates: string[]): string | null {
  if (d.base_date && d.base_date <= dates[dates.length - 1]) return d.base_date;
  const target = d.rcept_dt;
  const i = dates.findIndex((x) => x >= target);
  return i >= 0 ? dates[i] : null;
}

const catColor = (c: ThemeColors, key: Disclosure["category"]) => c[`cat-${key}` as keyof ThemeColors] as string;

export function PriceChart({ dates, close, kospi, ew, disclosures, selected, onSelect, mode, range, name }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{ main: ISeriesApi<"Area"> | ISeriesApi<"Line">; benches: ISeriesApi<"Line">[] } | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const colors = useThemeColors();
  const [hover, setHover] = useState<Hover | null>(null);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const start = useMemo(() => rangeStart(dates, range), [dates, range]);

  // 날짜별 공시 목록 (마커·툴팁·클릭 판정에 사용)
  const byDate = useMemo(() => {
    const m = new Map<string, Disclosure[]>();
    for (const d of disclosures) {
      const t = markerDate(d, dates);
      if (!t) continue;
      m.set(t, [...(m.get(t) ?? []), d]);
    }
    return m;
  }, [disclosures, dates]);

  const dateIndex = useMemo(() => new Map(dates.map((d, i) => [d, i])), [dates]);
  const byDateRef = useRef(byDate);
  useEffect(() => {
    byDateRef.current = byDate;
  }, [byDate]);

  // 차트 생성/재생성 (모드·테마가 바뀔 때)
  useEffect(() => {
    if (!box.current || !colors) return;
    const chart = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { color: colors.surface },
        textColor: colors["ink-3"],
        fontFamily: getComputedStyle(document.body).fontFamily,
        fontSize: 11,
        attributionLogo: true,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.14, bottom: 0.06 } },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true, rightOffset: 2 },
      crosshair: {
        mode: 0,
        vertLine: { color: colors["ink-3"], width: 1, style: 0, labelBackgroundColor: colors.ink },
        horzLine: { color: colors.axis, width: 1, style: 0, labelBackgroundColor: colors.ink },
      },
      localization: {
        locale: "ko-KR",
        priceFormatter: (v: number) => (mode === "price" ? fmtPrice(v) : v.toFixed(1)),
        timeFormatter: (t: Time) => String(t).replaceAll("-", "."),
      },
      handleScale: { axisPressedMouseMove: false },
    });

    let main: ISeriesApi<"Area"> | ISeriesApi<"Line">;
    const benches: ISeriesApi<"Line">[] = [];
    if (mode === "price") {
      main = chart.addSeries(AreaSeries, {
        lineColor: colors.ink,
        lineWidth: 2,
        topColor: withAlpha(colors.ink, colors.dark ? 0.14 : 0.08),
        bottomColor: withAlpha(colors.ink, 0),
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: colors.surface,
        crosshairMarkerBorderWidth: 2,
      });
    } else {
      benches.push(
        chart.addSeries(LineSeries, { color: colors["bench-1"], lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false }),
        chart.addSeries(LineSeries, { color: colors["bench-2"], lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false }),
      );
      main = chart.addSeries(LineSeries, {
        color: colors.ink,
        lineWidth: 2,
        priceLineVisible: false,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: colors.surface,
        crosshairMarkerBorderWidth: 2,
      });
    }
    chartRef.current = chart;
    seriesRef.current = { main, benches };
    markersRef.current = createSeriesMarkers(main, []);

    const onClick = (p: MouseEventParams<Time>) => {
      const id = (p.hoveredInfo?.objectId ?? p.hoveredObjectId) as string | undefined;
      if (typeof id === "string" && id) return onSelectRef.current(id);
      // 마커를 정확히 못 눌러도, 누른 날짜 ±1거래일에 공시가 있으면 선택 (터치 대응)
      if (!p.time) return;
      const i = dateIndex.get(String(p.time));
      if (i == null) return;
      for (const off of [0, -1, 1]) {
        const items = byDateRef.current.get(dates[i + off]);
        if (items?.length) return onSelectRef.current((items.find((x) => x.notable) ?? items[0]).rcept_no);
      }
    };
    const onMove = (p: MouseEventParams<Time>) => {
      const el = box.current;
      if (!el) return;
      const overMarker = p.hoveredInfo?.objectKind === "series-marker" || typeof p.hoveredObjectId === "string";
      el.style.cursor = overMarker ? "pointer" : "crosshair";
      if (!p.time || !p.point) return setHover(null);
      const t = String(p.time);
      const values: Hover["values"] = [];
      const mainData = p.seriesData.get(main) as { value?: number } | undefined;
      if (mainData?.value != null) values.push({ label: name, value: mode === "price" ? `${fmtPrice(mainData.value)}원` : mainData.value.toFixed(1), color: colors.ink });
      if (mode === "relative") {
        const [b1, b2] = benches.map((b) => (p.seriesData.get(b) as { value?: number } | undefined)?.value);
        if (b1 != null) values.push({ label: "코스피 동일가중", value: b1.toFixed(1), color: colors["bench-1"] });
        if (b2 != null) values.push({ label: "코스피", value: b2.toFixed(1), color: colors["bench-2"] });
      }
      setHover({ x: p.point.x, y: p.point.y, w: el.clientWidth, date: t, values, items: byDateRef.current.get(t) ?? [] });
    };
    chart.subscribeClick(onClick);
    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeClick(onClick);
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, colors, name]);

  // 데이터·기간
  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;
    if (mode === "price") {
      s.main.setData(dates.flatMap((d, i) => (close[i] == null ? [] : [{ time: d as Time, value: close[i] as number }])));
      s.benches.forEach((b) => b.setData([]));
      if (dates.length) chart.timeScale().setVisibleRange({ from: dates[start] as Time, to: dates[dates.length - 1] as Time });
    } else {
      const indexed = (arr: (number | null)[]) => {
        const base = arr.slice(start).find((v) => v != null);
        return dates.slice(start).flatMap((d, k) => {
          const v = arr[start + k];
          return v == null || !base ? [] : [{ time: d as Time, value: (v / base) * 100 }];
        });
      };
      s.main.setData(indexed(close));
      s.benches[0]?.setData(indexed(ew));
      s.benches[1]?.setData(indexed(kospi));
      chart.timeScale().fitContent();
    }
  }, [dates, close, kospi, ew, mode, start, colors]);

  // 마커
  useEffect(() => {
    const plugin = markersRef.current;
    if (!plugin || !colors) return;
    const from = mode === "relative" ? dates[start] : dates[0];
    const markers: SeriesMarker<Time>[] = [];
    for (const [t, items] of [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b))) {
      if (t < from) continue;
      for (const d of items) {
        const isSel = d.rcept_no === selected;
        markers.push({
          time: t as Time,
          position: CATEGORY_BY_KEY[d.category].row === "below" ? "belowBar" : "aboveBar",
          shape: "circle",
          color: catColor(colors, d.category),
          id: d.rcept_no,
          size: isSel ? 2.2 : d.notable ? 1.35 : 1,
          text: isSel ? CATEGORY_BY_KEY[d.category].short : undefined,
        });
      }
    }
    plugin.setMarkers(markers);
  }, [byDate, selected, colors, mode, start, dates]);

  // 선택한 공시가 화면 밖이면 보이게 이동
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !selected || mode !== "price") return;
    const d = disclosures.find((x) => x.rcept_no === selected);
    const t = d && markerDate(d, dates);
    if (!t) return;
    const vr = chart.timeScale().getVisibleRange();
    if (vr && (t < String(vr.from) || t > String(vr.to))) {
      const i = dateIndex.get(t) ?? 0;
      const span = Math.max(60, dates.length - start);
      chart.timeScale().setVisibleRange({
        from: dates[Math.max(0, i - Math.floor(span / 2))] as Time,
        to: dates[Math.min(dates.length - 1, i + Math.floor(span / 2))] as Time,
      });
    }
  }, [selected, disclosures, dates, dateIndex, mode, start]);

  return (
    <div className="relative" onMouseLeave={() => setHover(null)}>
      <div
        ref={box}
        className="h-[340px] sm:h-[400px] w-full"
        role="img"
        aria-label={`${name} 주가 차트. 점은 공시입니다. 공시 목록은 아래 '공시 이력' 탭에서 표로 볼 수 있습니다.`}
      />
      {!colors && <div className="absolute inset-0 grid place-items-center text-sm text-ink-3">차트 불러오는 중…</div>}
      {hover && (hover.values.length > 0 || hover.items.length > 0) && <Tooltip hover={hover} colors={colors} />}
    </div>
  );
}

function Tooltip({ hover, colors }: { hover: Hover; colors: ThemeColors | null }) {
  const left = hover.x > hover.w - 250 ? hover.x - 236 : hover.x + 14;
  return (
    <div className="pointer-events-none absolute z-10 w-[222px] card px-3 py-2.5 text-xs animate-fade-up" style={{ left, top: Math.max(4, hover.y - 30) }}>
      <div className="text-ink-3 tnum">{hover.date.replaceAll("-", ".")}</div>
      {hover.values.map((v) => (
        <div key={v.label} className="flex items-center justify-between gap-2 mt-1">
          <span className="flex items-center gap-1.5 text-ink-2 truncate">
            <span className="w-2.5 h-[2px] rounded" style={{ background: v.color }} aria-hidden />
            {v.label}
          </span>
          <span className="font-semibold text-ink tnum">{v.value}</span>
        </div>
      ))}
      {hover.items.length > 0 && (
        <div className="mt-2 pt-2 border-t border-line space-y-1.5">
          {hover.items.slice(0, 4).map((d) => (
            <div key={d.rcept_no} className="flex gap-1.5 items-start">
              <span className="mt-[5px] w-2 h-2 rounded-full shrink-0" style={{ background: colors ? catColor(colors, d.category) : undefined }} aria-hidden />
              <span className="text-ink leading-snug">
                {groupLabel(d.group_key)}
                {d.impact?.headline && <span className="block text-ink-3">{d.impact.headline}</span>}
              </span>
            </div>
          ))}
          {hover.items.length > 4 && <div className="text-ink-3">외 {hover.items.length - 4}건</div>}
          <div className="text-ink-3">클릭하면 자세히</div>
        </div>
      )}
    </div>
  );
}
