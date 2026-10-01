// 숫자·날짜 표시 형식 (한국 증시 관례)

export function krw(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return "–";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${(n / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: digits })}조`;
  if (abs >= 1e8) return `${Math.round(n / 1e8).toLocaleString("ko-KR")}억`;
  if (abs >= 1e4) return `${Math.round(n / 1e4).toLocaleString("ko-KR")}만`;
  return Math.round(n).toLocaleString("ko-KR");
}

export function price(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "–";
  return Math.round(n).toLocaleString("ko-KR");
}

/** 비율(0.021) → "+2.1%" */
export function pct(x: number | null | undefined, digits = 1, signed = true): string {
  if (x == null || !Number.isFinite(x)) return "–";
  let v = x * 100;
  if (Math.abs(v) < 0.5 * 10 ** -digits) v = 0; // "-0.0%" 방지
  const s = v.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return signed && v > 0 ? `+${s}%` : `${s}%`;
}

/** 이미 % 단위인 값(12.3) → "+12.3%" */
export function pctRaw(v: number | null | undefined, digits = 1, signed = true): string {
  if (v == null || !Number.isFinite(v)) return "–";
  return pct(v / 100, digits, signed);
}

export function multiple(x: number | null | undefined, digits = 1): string {
  if (x == null || !Number.isFinite(x)) return "–";
  return `${x.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}배`;
}

/** 상승=빨강, 하락=파랑 (한국 관례) */
const ZERO = 0.0005; // 표시상 0.0%면 보합으로 취급

export function signClass(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x) || Math.abs(x) < ZERO) return "text-ink-2";
  return x > 0 ? "text-up" : "text-down";
}

export function arrow(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x) || Math.abs(x) < ZERO) return "";
  return x > 0 ? "▲" : "▼";
}

export function date(d: string | null | undefined): string {
  if (!d) return "–";
  return d.slice(0, 10).replaceAll("-", ".");
}

export function shortDate(d: string | null | undefined): string {
  if (!d) return "–";
  return `${Number(d.slice(5, 7))}.${Number(d.slice(8, 10))}`;
}

export function time(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  return t.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Seoul" });
}

/** 피드용: 오늘이면 "14:32", 아니면 "9.24 14:32" */
export function feedTime(iso: string, now = Date.now()): string {
  const kst = (t: number) => new Date(t + 9 * 3600_000).toISOString().slice(0, 10);
  const t = new Date(iso).getTime();
  const hm = time(iso) ?? "";
  return kst(t) === kst(now) ? hm : `${shortDate(kst(t))} ${hm}`;
}

export function relative(iso: string, now = Date.now()): string {
  const diff = Math.max(0, now - new Date(iso).getTime());
  const m = Math.floor(diff / 60000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  return `${d}일 전`;
}
