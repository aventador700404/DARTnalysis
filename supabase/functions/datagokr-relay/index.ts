// 공공데이터포털(금융위원회 주식·지수 시세) 중계.
// apis.data.go.kr 은 해외(GitHub Actions 등)에서 접속이 막혀서, 서울 리전에서 대신 요청한다.
// 계산·저장 없이 요청을 그대로 전달만 함 (리소스 최소).
//
// 호출: GET /functions/v1/datagokr-relay?svc=stock|index&<원래 파라미터>
//   헤더 x-region: ap-northeast-2   ← 반드시 서울에서 실행되도록
//   헤더 x-relay-secret: <중계 비밀값>
// 필요한 비밀값 (supabase secrets set ...): DATAGOKR_SERVICE_KEY 하나뿐.
// 중계 비밀값은 DB Vault에 자동 생성돼 있음 (migrations/0004) → service role로 꺼내 씀.
// JWT 검사는 끄고(config.toml) x-relay-secret 으로 인증한다.

const BASE = "https://apis.data.go.kr/1160100/service";
const TARGETS: Record<string, string> = {
  stock: `${BASE}/GetStockSecuritiesInfoService/getStockPriceInfo`,
  index: `${BASE}/GetMarketIndexInfoService/getStockMarketIndex`,
};
const DROP = new Set(["svc", "serviceKey", "forceFunctionRegion"]);

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

// service role 키: 기존 방식(SUPABASE_SERVICE_ROLE_KEY) 또는 새 방식(SUPABASE_SECRET_KEYS JSON)
function serviceKey(): string | undefined {
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (legacy) return legacy;
  try {
    return JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}").default;
  } catch {
    return undefined;
  }
}

// 중계 비밀값: 인스턴스당 한 번만 DB에서 읽고 재사용
let relaySecret: Promise<string | undefined> | undefined;
function getRelaySecret(): Promise<string | undefined> {
  relaySecret ??= (async () => {
    const key = serviceKey();
    const url = Deno.env.get("SUPABASE_URL");
    if (!key || !url) return undefined;
    const r = await fetch(`${url}/rest/v1/rpc/datagokr_relay_secret`, {
      method: "POST",
      headers: { apikey: key, Authorization: `Bearer ${key}`, "content-type": "application/json" },
      body: "{}",
    });
    return r.ok ? ((await r.json()) as string | null) ?? undefined : undefined;
  })().catch(() => undefined);
  return relaySecret.then((v) => {
    if (!v) relaySecret = undefined; // 실패는 캐시하지 않음
    return v;
  });
}

// 길이·내용이 달라도 걸리는 시간이 같은 비교 (비밀값 추측 방지)
function sameSecret(a: string, b: string): boolean {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

Deno.serve(async (req) => {
  const dataKey = Deno.env.get("DATAGOKR_SERVICE_KEY");
  if (!dataKey) return json(500, { error: "relay not configured: set DATAGOKR_SERVICE_KEY in Edge Function secrets" });
  const secret = await getRelaySecret();
  if (!secret) return json(500, { error: "relay not configured: vault secret datagokr_relay_secret missing" });
  if (req.method !== "GET") return json(405, { error: "GET only" });
  if (!sameSecret(req.headers.get("x-relay-secret") ?? "", secret)) return json(401, { error: "unauthorized" });

  const incoming = new URL(req.url);
  const target = TARGETS[incoming.searchParams.get("svc") ?? ""];
  if (!target) return json(400, { error: "svc must be stock or index" });

  const out = new URL(target);
  for (const [k, v] of incoming.searchParams) if (!DROP.has(k)) out.searchParams.set(k, v);
  out.searchParams.set("serviceKey", dataKey);

  try {
    const r = await fetch(out, { signal: AbortSignal.timeout(50_000) });
    return new Response(r.body, {
      status: r.status,
      headers: {
        "content-type": r.headers.get("content-type") ?? "application/json",
        "x-relay-region": Deno.env.get("SB_REGION") ?? "",
      },
    });
  } catch (e) {
    return json(502, { error: `upstream fetch failed: ${(e as Error).name}` });
  }
});
