"use client";

import { groupLabel } from "@/lib/categories";
import { date, krw, pct, pctRaw, price, relative, time } from "@/lib/format";
import type { Benchmark, Disclosure, Impact, NewsItem, StatRow } from "@/lib/types";
import { CategoryTag, Delta } from "../ui";
import { RangeBar } from "./RangeBar";

const BM_LABEL: Record<Benchmark, string> = { ew: "코스피 동일가중", kospi: "코스피" };

export function DisclosurePanel({
  d,
  stats,
  benchmark,
  news,
  demo,
  onPrev,
  onNext,
  position,
}: {
  d: Disclosure | null;
  stats: StatRow[];
  benchmark: Benchmark;
  news: NewsItem[];
  demo: boolean;
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
  position: string;
}) {
  if (!d) {
    return (
      <div className="h-full grid place-items-center text-center p-6">
        <div>
          <div className="mx-auto w-10 h-10 rounded-full bg-surface-2 grid place-items-center mb-3" aria-hidden>
            <span className="w-3 h-3 rounded-full bg-[var(--cat-buyback)]" />
          </div>
          <p className="text-sm font-medium">차트의 점(공시)을 눌러보세요</p>
          <p className="text-xs text-ink-3 mt-1 leading-relaxed">
            공시 뒤 주가가 시장보다 얼마나 움직였는지,
            <br />
            회사 숫자는 어떻게 바뀌었는지 보여드려요.
          </p>
        </div>
      </div>
    );
  }

  const ex = (h: 5 | 20) => d[`ex_${benchmark}_${h}` as keyof Disclosure] as number | null;
  const groupStats = (h: number) => stats.find((s) => s.group_key === d.group_key && s.horizon === h && s.benchmark === benchmark);
  const related = news.filter((n) => n.rcept_no === d.rcept_no);
  const seen = time(d.first_seen_at);

  return (
    <div className="flex flex-col h-full animate-fade-up" key={d.rcept_no}>
      <div className="px-4 sm:px-5 pt-4 pb-3 border-b border-line">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <CategoryTag category={d.category} label={groupLabel(d.group_key)} />
            {d.notable && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-brand-soft text-brand-ink">주목</span>}
            {d.is_correction && <span className="text-[11px] px-2 py-0.5 rounded-full bg-surface-2 text-ink-3">정정공시</span>}
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            <span className="text-[11px] text-ink-3 tnum mr-1">{position}</span>
            <NavButton onClick={onPrev} label="이전 공시" dir="left" />
            <NavButton onClick={onNext} label="다음 공시" dir="right" />
          </div>
        </div>
        <h3 className="mt-2 text-[15px] font-semibold leading-snug tracking-[-0.02em] break-keep">{d.report_nm}</h3>
        <p className="mt-1 text-xs text-ink-3 tnum">
          접수 {date(d.rcept_dt)}
          {seen && ` · 처음 발견 ${seen}`}
          {d.base_date && ` · 기준일 ${date(d.base_date)}`}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto thin-scroll px-4 sm:px-5 py-4 space-y-5">
        {/* 이후 주가 */}
        <section>
          <h4 className="text-xs font-semibold text-ink-2">
            이후 주가 <span className="font-normal text-ink-3">· {BM_LABEL[benchmark]} 대비 초과수익률</span>
          </h4>
          {d.excluded_reason ? (
            <p className="mt-2 text-xs text-ink-3 bg-surface-2 rounded-lg px-3 py-2">통계에서 제외된 공시예요: {d.excluded_reason}</p>
          ) : (
            <div className="mt-2 grid grid-cols-2 gap-2">
              {([5, 20] as const).map((h) => (
                <div key={h} className="rounded-xl bg-surface-2 px-3 py-2.5">
                  <div className="text-[11px] text-ink-3">{h}거래일 후</div>
                  {ex(h) == null ? (
                    <div className="text-xs text-ink-3 mt-1.5">아직 {h}거래일이 지나지 않았어요</div>
                  ) : (
                    <>
                      <Delta value={ex(h)} className="block text-xl font-bold tracking-[-0.02em] mt-0.5" />
                      <div className="text-[11px] text-ink-3 mt-0.5 tnum">주가 자체 {pct(d[`ret_${h}`])}</div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 재무 영향 */}
        <section>
          <h4 className="text-xs font-semibold text-ink-2">회사 숫자는 어떻게 바뀌나</h4>
          <ImpactBlock impact={d.impact} category={d.category} />
        </section>

        {/* 같은 유형 과거 반응 */}
        <section>
          <h4 className="text-xs font-semibold text-ink-2">
            같은 유형 과거 반응 <span className="font-normal text-ink-3">· {groupLabel(d.group_key)}</span>
          </h4>
          <div className="mt-2 space-y-3">
            {([5, 20] as const).map((h) => {
              const s = groupStats(h);
              if (!s) return null;
              if (s.hidden || s.median == null)
                return (
                  <p key={h} className="text-xs text-ink-3">
                    {h}거래일: 표본 {s.n}건 — 5건 미만이라 표시하지 않아요
                  </p>
                );
              return (
                <div key={h}>
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="text-ink-2">{h}거래일</span>
                    <span className="text-ink-3 tnum">
                      평균 <b className="text-ink font-semibold">{pct(s.mean)}</b> · 중앙값 {pct(s.median)} · 오른 비율 {pct(s.up_ratio, 0, false)} · {s.n}건
                    </span>
                  </div>
                  <div className="mt-1.5">
                    <RangeBar p10={s.p10!} p25={s.p25!} median={s.median} p75={s.p75!} p90={s.p90!} value={d.excluded_reason ? null : ex(h)} label={`${h}거래일 초과수익률 분포`} />
                  </div>
                </div>
              );
            })}
            <p className="text-[11px] text-ink-3 leading-relaxed">
              막대: 과거 같은 유형 공시들의 가운데 50%(진한 부분)와 80% 범위 · 세로선: 중앙값 · <span className="text-brand-ink">●</span> 이 공시. 평균은
              상·하위 1%를 잘라낸 값이에요.
            </p>
          </div>
        </section>

        {/* 뉴스 */}
        {related.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-ink-2">관련 뉴스 {demo && <span className="font-normal text-ink-3">· 가상 뉴스</span>}</h4>
            <ul className="mt-2 space-y-2">
              {related.map((n) => (
                <li key={`${n.title}-${n.published_at}`} className="text-sm leading-snug">
                  {n.url ? (
                    <a href={n.url} target="_blank" rel="noreferrer" className="hover:underline">
                      {n.title}
                    </a>
                  ) : (
                    <span>{n.title}</span>
                  )}
                  <span className="block text-[11px] text-ink-3 mt-0.5">
                    {n.source}
                    {n.published_at && ` · ${relative(n.published_at)}`}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <div className="sticky -bottom-4 h-8 -mt-8 bg-gradient-to-t from-[var(--surface)] to-transparent pointer-events-none" aria-hidden />
      </div>

      <div className="px-4 sm:px-5 py-3 border-t border-line text-xs">
        {demo ? (
          <span className="text-ink-3">샘플 데이터라 DART 원문 링크가 없어요</span>
        ) : (
          <a href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${d.rcept_no}`} target="_blank" rel="noreferrer" className="font-medium text-brand-ink hover:underline">
            DART 원문 보기 ↗
          </a>
        )}
      </div>
    </div>
  );
}

function NavButton({ onClick, label, dir }: { onClick: (() => void) | null; label: string; dir: "left" | "right" }) {
  return (
    <button
      type="button"
      onClick={onClick ?? undefined}
      disabled={!onClick}
      aria-label={label}
      title={label}
      className="w-7 h-7 grid place-items-center rounded-lg text-ink-2 hover:bg-surface-2 disabled:opacity-30 disabled:hover:bg-transparent"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
        <path d={dir === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"} stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function Row({ k, v }: { k: string; v: string | number | null | undefined }) {
  if (v == null || v === "" || v === "–") return null;
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-line last:border-0">
      <dt className="text-ink-3">{k}</dt>
      <dd className="text-ink tnum text-right">{v}</dd>
    </div>
  );
}

function ImpactBlock({ impact, category }: { impact: Impact | null; category: Disclosure["category"] }) {
  if (!impact) {
    return (
      <p className="mt-2 text-xs text-ink-3 bg-surface-2 rounded-lg px-3 py-2 leading-relaxed">
        {category === "earnings"
          ? "실적 공시예요. 바뀐 숫자는 아래 '재무 추이' 탭에서 볼 수 있어요."
          : "이 유형은 주식 수·지분을 바꾸지 않아서 재무 영향 계산 대상이 아니에요."}
      </p>
    );
  }
  const m = impact.metrics as Record<string, number | string | null>;
  const n = (k: string) => (typeof m[k] === "number" ? (m[k] as number) : null);
  return (
    <div className="mt-2 rounded-xl border border-line px-3 py-2.5">
      <p className="text-sm font-semibold tracking-[-0.01em]">{impact.headline}</p>
      <dl className="mt-2 text-xs">
        {impact.kind === "rights_offering" && (
          <>
            <Row k="새로 발행하는 주식" v={n("new_shares") != null ? `${price(n("new_shares"))}주` : null} />
            <Row k="증자 전 주식 수" v={n("shares_before") != null ? `${price(n("shares_before"))}주` : null} />
            <Row k="조달 금액" v={n("raise_amount") != null ? `${krw(n("raise_amount"))}원` : null} />
            <Row k="주요 목적" v={m.main_purpose as string} />
            <Row k="방식" v={m.method as string} />
          </>
        )}
        {(impact.kind === "cb" || impact.kind === "bw") && (
          <>
            <Row k="발행 총액" v={n("face_amount") != null ? `${krw(n("face_amount"))}원` : null} />
            <Row k={impact.kind === "cb" ? "전환가" : "행사가"} v={n("conversion_price") != null ? `${price(n("conversion_price"))}원` : null} />
            <Row k="늘어날 수 있는 주식" v={n("potential_shares") != null ? `${price(n("potential_shares"))}주` : null} />
          </>
        )}
        {impact.kind === "buyback" && (
          <>
            <Row k="취득 예정 주식" v={n("planned_shares") != null ? `${price(n("planned_shares"))}주` : null} />
            <Row k="취득 예정 금액" v={n("planned_amount") != null ? `${krw(n("planned_amount"))}원` : null} />
            <Row k="시가총액 대비" v={pctRaw(n("amount_vs_mcap_pct"), 2, false)} />
            <Row k="방법" v={m.method as string} />
          </>
        )}
        {impact.kind === "treasury_disposal" && (
          <>
            <Row k="처분 예정 주식" v={n("planned_shares") != null ? `${price(n("planned_shares"))}주` : null} />
            <Row k="처분 예정 금액" v={n("planned_amount") != null ? `${krw(n("planned_amount"))}원` : null} />
          </>
        )}
        {(impact.kind === "major_holder" || impact.kind === "insider") && (
          <>
            <Row k="보고자" v={m.holder as string} />
            <Row k="보고 후 지분율" v={n("stake_pct") != null ? `${n("stake_pct")!.toFixed(2)}%` : null} />
            <Row k="변동" v={n("stake_change_pp") != null ? `${n("stake_change_pp")! > 0 ? "+" : ""}${n("stake_change_pp")!.toFixed(2)}%p` : null} />
          </>
        )}
      </dl>
    </div>
  );
}
