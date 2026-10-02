-- DARTanalysis 초기 스키마 (명세서 5.4)
-- Supabase 대시보드 > SQL Editor 에 붙여넣고 실행하거나, supabase CLI로 `supabase db push`.

-- ── 종목 ───────────────────────────────────────────────
create table if not exists public.companies (
  code          text primary key,            -- 종목코드 6자리
  corp_code     text unique,                 -- DART 고유번호 8자리
  name          text not null,
  market        text not null default 'KOSPI',
  ksic          text,                        -- 업종코드 앞 3자리 (공식 분류)
  ksic_name     text,
  themes        text[] not null default '{}',-- 투자 테마 (직접 설계한 분류, 여러 개 가능)
  is_financial  boolean not null default false,
  updated_at    timestamptz not null default now()
);

-- ── 주가 (공공데이터포털, 하루 지연 · 수정주가 아님) ─────────
create table if not exists public.prices_daily (
  code        text not null references public.companies(code) on delete cascade,
  date        date not null,
  open        numeric,
  high        numeric,
  low         numeric,
  close       numeric not null,
  volume      bigint,
  market_cap  numeric,
  shares      bigint,
  primary key (code, date)
);
create index if not exists prices_daily_date_idx on public.prices_daily (date);

-- ── 벤치마크 ──────────────────────────────────────────
create table if not exists public.index_daily (
  date      date primary key,
  kospi     numeric,   -- 코스피 지수 (시가총액 가중)
  kospi_ew  numeric    -- 코스피 전 종목 동일가중 평균 (직접 계산, 시작=100)
);

-- ── 재무 (분기별 값으로 변환한 결과) ───────────────────────
create table if not exists public.financials (
  code                   text not null references public.companies(code) on delete cascade,
  year                   int  not null,
  quarter                int  not null check (quarter between 1 and 4),
  period_end             date,
  available_from         date,     -- 보고서 공시일: 이 날부터 이 숫자를 쓸 수 있음 (미래 정보 방지)
  fs_div                 text,     -- CFS 연결 / OFS 별도
  revenue                numeric,
  operating_income       numeric,
  net_income             numeric,
  net_income_parent      numeric,
  interest_expense       numeric,
  operating_cash_flow    numeric,
  total_assets           numeric,
  total_liabilities      numeric,
  total_equity           numeric,
  equity_parent          numeric,
  ttm_revenue            numeric,
  ttm_operating_income   numeric,
  ttm_net_income_parent  numeric,
  roe                    numeric,
  op_margin              numeric,
  debt_ratio             numeric,
  primary key (code, year, quarter)
);

create table if not exists public.annual_facts (
  code            text not null references public.companies(code) on delete cascade,
  year            int not null,
  dividend_total  numeric,   -- 현금배당금 총액 (원)
  audit_opinion   text,
  primary key (code, year)
);

-- ── 공시 ──────────────────────────────────────────────
create table if not exists public.disclosures (
  rcept_no       text primary key,   -- DART 접수번호 14자리
  code           text not null references public.companies(code) on delete cascade,
  corp_code      text,
  report_nm      text not null,
  rcept_dt       date not null,
  first_seen_at  timestamptz default now(),  -- 실시간 수집이 처음 발견한 시각 (기준일 판단에 사용)
  category       text not null,     -- 마커 유형 5종
  subtype        text,              -- 세부 유형 (재무 영향 계산용)
  group_key      text not null,     -- 유형별 통계 묶음 키
  is_correction  boolean not null default false,
  detail         jsonb,             -- 주요사항보고서·지분공시 상세 응답
  news_followup_at timestamptz,     -- 30분 뒤 뉴스 재검색 예정 시각
  created_at     timestamptz not null default now()
);
create index if not exists disclosures_code_dt_idx on public.disclosures (code, rcept_dt desc);
create index if not exists disclosures_dt_idx on public.disclosures (rcept_dt desc);

create table if not exists public.disclosure_impacts (
  rcept_no         text primary key references public.disclosures(rcept_no) on delete cascade,
  code             text not null,
  group_key        text not null,
  base_date        date,
  ret_5            numeric,
  ret_20           numeric,
  ex_kospi_5       numeric,
  ex_kospi_20      numeric,
  ex_ew_5          numeric,
  ex_ew_20         numeric,
  excluded_reason  text,
  impact           jsonb,           -- 재무 영향 (희석률 등) + 화면 문구
  notable          boolean not null default false,
  updated_at       timestamptz not null default now()
);
create index if not exists disclosure_impacts_code_idx on public.disclosure_impacts (code);

create table if not exists public.disclosure_stats (
  group_key    text not null,
  horizon      int  not null,
  benchmark    text not null check (benchmark in ('kospi', 'ew')),
  group_label  text,
  category     text,
  n            int not null,
  hidden       boolean not null,     -- 표본 5건 미만이면 true (화면에서 숨김)
  mean         numeric,
  median       numeric,
  up_ratio     numeric,
  p10 numeric, p25 numeric, p75 numeric, p90 numeric,
  updated_at   timestamptz not null default now(),
  primary key (group_key, horizon, benchmark)
);

-- ── 종목 건강검진 · 밸류에이션 ─────────────────────────────
create table if not exists public.scores (
  code                text primary key references public.companies(code) on delete cascade,
  as_of               date not null,
  growth              numeric,
  profitability       numeric,
  stability           numeric,
  value               numeric,
  shareholder_return  numeric,
  metric_scores       jsonb,
  basis               jsonb,
  note                text
);

create table if not exists public.valuation (
  code                 text primary key references public.companies(code) on delete cascade,
  as_of                date not null,
  market_cap           numeric,
  per numeric, pbr numeric, per_band_pct numeric, pbr_band_pct numeric,
  roe numeric, op_margin numeric, debt_ratio numeric, interest_coverage numeric,
  revenue_cagr_3y numeric, op_income_cagr_3y numeric,
  dividend_yield numeric, buyback_yield numeric,
  ttm_revenue numeric, ttm_operating_income numeric
);

create table if not exists public.valuation_history (
  code  text not null references public.companies(code) on delete cascade,
  date  date not null,   -- 월말
  per   numeric,
  pbr   numeric,
  primary key (code, date)
);

-- ── 뉴스 · 호출 기록 ──────────────────────────────────────
create table if not exists public.news (
  id            bigint generated always as identity primary key,
  code          text not null references public.companies(code) on delete cascade,
  rcept_no      text references public.disclosures(rcept_no) on delete set null,
  title         text not null,
  summary       text,
  url           text not null unique,
  source        text,
  published_at  timestamptz,
  created_at    timestamptz not null default now()
);
create index if not exists news_code_idx on public.news (code, published_at desc);

create table if not exists public.api_usage (
  day    date not null,
  api    text not null,
  calls  int  not null,
  primary key (day, api)
);

-- ── 보안: 외부(anon)는 읽기만, 쓰기는 파이프라인(DB 직접 연결·service role)만 ─────
do $$
declare t text;
begin
  foreach t in array array['companies','prices_daily','index_daily','financials','annual_facts','disclosures',
                           'disclosure_impacts','disclosure_stats','scores','valuation','valuation_history','news']
  loop
    execute format('alter table public.%I enable row level security', t);
    -- drop 없이 '없을 때만 생성' → 다시 실행해도 안전하고 삭제 확인이 필요 없음
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'public read') then
      execute format('create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    end if;
  end loop;
  -- api_usage는 공개하지 않음 (RLS만 켜고 정책 없음 → anon 접근 불가)
  execute 'alter table public.api_usage enable row level security';
end $$;
