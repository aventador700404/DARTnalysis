# CLAUDE.md — DARTanalysis (공시차트)

Claude Code가 이 저장소에서 작업할 때 먼저 읽는 안내서. 사람용 설명은 README.md.

## 이 프로젝트는

**공시가 뜰 때마다 주가가 어떻게 움직였고 회사 숫자는 어떻게 바뀌었는지를, 종목의 재무 체력과 함께 차트 위에서 보여주는 DART 기반 주가 분석 대시보드.**

- 목적: 포트폴리오용 웹 서비스 (바이브코딩으로 어디까지 만들 수 있는지 보여주기). 투자 추천 서비스 아님.
- 범위 v1: 코스피 전 종목. v2 후보: 코스닥150.
- UI 레퍼런스: FACT CHART (factchart.co.kr) — 주가 차트 위 공시 마커.
- 기능 명세서: Notion "DART 공시·주가 분석 대시보드 — 기능 명세서 v0.1". 아래 '명세서와 달라진 점'이 최신.
- 서비스 이름 `공시차트`는 임시. `web/lib/site.ts` 한 곳에서만 바꿈.

## 작업 방식

- 사용자는 비개발자 관점의 설명을 선호함. 전문용어만 던지지 말고, 무엇을 왜 바꾸는지 쉬운 말로 설명.
- 큰 기능은 먼저 기능 명세와 로직 설명을 짧게 합의한 뒤 구현.
- UI는 레퍼런스 충실도를 중요하게 봄. 폰트·간격·애니메이션까지 신경 쓰기.
- 변경 후에는 아래 '검증' 명령을 돌리고 결과를 알려주기.

## 구조

```
web/        Next.js 16 (App Router) · Tailwind 4 · lightweight-charts 5 · recharts 3 · supabase-js
  app/                    / (홈) · /stock/[code] (종목) · /sectors (업종 비교)
  components/stock/       PriceChart(공시 마커 차트) · DisclosurePanel · HealthTab · FinancialsTab · HistoryTab · PeersTab · StockView(화면 상태, URL 동기화)
  components/home/        LiveFeed(실시간 피드) · MarketChart · ThemeHeatmap · TypeReactions
  lib/data/               index.ts(DATA_SOURCE 분기) · mock.ts(샘플 JSON) · supabase.ts(실데이터)
  lib/                    types.ts · categories.ts(마커 유형·색) · format.ts · useThemeColors.ts · site.ts
  lib/mock/data.json      가상 기업 샘플 데이터 (pipeline이 생성 — 직접 수정 금지)
pipeline/   Python 3.11+
  dartpipe/clients/       dart.py · datagokr.py · naver.py · http.py(재시도·호출 예산)
  dartpipe/               classify · financials(분기 변환) · event_study · impact · valuation · health · benchmark · analyze(전체 계산) · store(Postgres)
  dartpipe/jobs/          backfill · daily · check_apis · common
  dartpipe/mock/          generate.py (가상 기업 → 실제 분석 함수 통과 → web/lib/mock/data.json)
  tests/                  pytest 38개 (test_jobs_db는 pgserver로 로컬 Postgres 띄워 백필 전체 흐름 검증)
supabase/   migrations/0001~0004 · functions/poll-disclosures (1분 공시 폴링) · functions/datagokr-relay (공공데이터포털 서울 중계) · functions/_shared/classify.ts · cron.sql · config.toml
.github/workflows/   ci.yml(테스트·린트·빌드) · daily-batch.yml(평일 KST 20:17, 키 없으면 건너뜀)
```

## 명령어

```bash
# 웹 (키 없이 샘플 데이터로 실행)
cd web && npm install && npm run dev        # http://localhost:3000
npm run lint && npm run build               # 수정 후 반드시

# 파이프라인
cd pipeline && pip install -r requirements.txt pgserver
python -m pytest -q                         # 38개 통과해야 함
python -m dartpipe.mock.generate            # 샘플 데이터 재생성 (분석 로직 바꾸면 실행)
python -m dartpipe.jobs.check_apis          # 실제 API 키 동작 확인 (.env 필요)
python -m dartpipe.jobs.backfill --years 1 --limit 20   # 시험 백필 (SUPABASE_DB_URL 필요)
```

**Next.js 16 주의:** 학습 데이터와 API가 다를 수 있음. `web/AGENTS.md` 안내대로 `web/node_modules/next/dist/docs/` 를 먼저 확인. 예) `params`·`searchParams`는 Promise, `PageProps<'/stock/[code]'>` 타입은 `npx next typegen`으로 생성.

## 반드시 지킬 규칙 (설계 결정)

1. **공시 분류는 두 곳이 같아야 함:** `pipeline/dartpipe/classify.py` ↔ `supabase/functions/_shared/classify.ts`. 하나를 바꾸면 다른 쪽도 바꾸고, 같은 공시 제목 목록으로 결과가 같은지 확인.
2. **마커 유형은 5개:** earnings(실적) · financing(증자·감자·CB) · buyback(자사주) · ownership(지분) · other(기타). `classify.py CATEGORIES` ↔ `web/lib/categories.ts` 동기화.
   - 차트에서 두 줄로 찍음: 위(aboveBar) = financing·buyback·other, 아래(belowBar) = earnings·ownership.
   - 색은 같은 줄 안의 조합이 색약·정상 시각 모두 구분되도록 검증한 값 (`web/app/globals.css`의 `--cat-*`). 색을 바꾸거나 유형을 늘리면 다시 검증할 것. 유형을 늘리고 싶으면 색을 추가하기보다 '기타'로 묶거나 줄을 나누는 방식으로.
3. **상승=빨강, 하락=파랑** (한국 관례). `--up`, `--down` 토큰만 사용. 텍스트에 차트 시리즈 색을 쓰지 않음.
4. **색은 CSS 변수 토큰으로만.** 라이트/다크 둘 다 `globals.css`에 정의. 캔버스 차트(lightweight-charts)는 `useThemeColors()`로 실제 색을 읽어서 넘김.
5. **공시 후 수익률:** 기준일 = 장 마감(15:30) 전 처음 발견 → 당일, 그 외·시각 모름 → 다음 거래일. 수익률 = 기준일 전날 종가 → h번째 거래일 종가. 초과수익률 = 종목 − 벤치마크.
6. **기본 벤치마크는 코스피 동일가중 평균**(`benchmark.py`가 직접 계산). 코스피 지수는 대형주 쏠림이 커서 보조로만.
7. **통계 노출 규칙:** 표본 5건 미만 숨김, 평균은 상·하위 1% 자른 값, 중앙값·오른 비율·표본 수 함께 표시. 거래정지·상장주식 수 20% 이상 변화(분할·병합)·초소형주는 제외. 파라미터는 `pipeline/dartpipe/config.py`.
8. **재무:** 분·반기 보고서는 누적 → 차분해서 분기 값(4Q = 연간 − 3Q 누적, 현금흐름표는 누적만 줌). 재무 숫자는 보고서 공시일(`available_from`)부터만 사용 (미래 정보 방지).
9. **건강검진:** 5개 항목 = 업종(투자 테마) 내 백분위, 임의 가중치·합산 없음. 업종 회사 5개 미만이면 코스피 전체 기준. 금융업은 v1 계산 제외.
10. **실시간 주가 표시 금지:** 거래소 시세를 공개 웹에 보여주려면 정보이용계약이 필요. 주가는 공공데이터포털 일별(하루 지연), 공시·뉴스만 실시간.
11. **샘플 데이터는 가상 기업만:** 종목코드 `X`로 시작, 실제 회사명·실제 공시를 샘플에 쓰지 않음. 화면에 '샘플 데이터' 표시 유지.
12. **비밀값:** API 키·DB 연결 문자열은 `.env` / GitHub Secrets / Supabase secrets에만. 코드·커밋·로그에 넣지 않기. 웹에는 읽기 전용 anon 키만.
13. **크론 시간은 UTC** (KST − 9시간). `supabase/cron.sql`, `daily-batch.yml` 수정 시 변환 확인.

## 명세서와 달라진 점 (v0.1 구현 중 결정)

- 마커 유형 6 → 5개: '증자·감자'와 '전환사채'를 '자금조달(financing)'로 합침 — 6개 색으로는 색 구분 검증을 통과 못 해서.
- 마커를 위·아래 두 줄로 분리.
- 파이프라인은 Supabase REST 대신 Postgres 직접 연결(`SUPABASE_DB_URL`, Session pooler) — 대량 읽기·쓰기 속도 때문.

## 현재 상태

- ✅ 웹 빌드·린트 통과, 샘플 데이터로 전 화면 동작 (데스크톱·모바일·다크 확인)
- ✅ 파이프라인 테스트 38개 통과 (로컬 Postgres 백필 통합 테스트 포함), Python·TS 분류 결과 일치 확인
- ✅ **OpenDART 실제 호출 확인 (2026-10-02):** 공시검색·전체 재무제표 응답 필드가 코드와 일치, 수정 불필요. 공시 제목 끝에 공백이 붙어 오지만 분류(Py·TS)에서 trim함.
- ✅ **공공데이터포털 실제 호출 확인 (2026-10-09, 서울 중계 경유):** 주식·지수 모두 정상. **반드시 V2 주소**(`/1160100/GetStockSecuritiesInfoService_V2/getStockPriceInfo_V2`, `/1160100/GetMarketIndexInfoService_V2/getStockMarketIndex_V2`) — 예전 `/1160100/service/...` 주소는 승인된 키로도 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`가 남(한참 헤맨 원인). 응답 필드는 `to_price_row`·지수 `clpr`와 일치. 키는 64자리 hex(Encoding=Decoding).
- ✅ **시험 백필 성공 (2026-10-09, GitHub Actions, years=1 limit=20):** companies 20 · prices_daily 4,860 · index_daily 243 · financials 200 · disclosures 1,569(→impacts 1,569, stats 52) · scores·valuation 20. DART 1,114회·공공데이터 51회, 53분.
  - OpenDART `corpCode.xml`이 점검(status 800)이면 최근 정기공시 목록으로 회사 매핑을 대신 만듦(`common.corp_codes_by_stock`).
  - DART 전체재무제표 호출이 건당 10초 넘게 걸릴 때가 있음 → 전체 백필(825개사) 전에 속도·하루 호출 한도(2만) 계산 필요.
  - 지주회사(KSIC 64992)는 금융지주·일반 지주가 같은 코드 → 이름('금융' 포함, 신한지주)으로 금융업 판정(`ksic.is_financial`).
- ⏸ 네이버 뉴스: 키 미등록, 당분간 제외하고 진행.
- Claude Code 클라우드 세션: 환경 설정 Network access=Custom에 `opendart.fss.or.kr`, `apis.data.go.kr`, `openapi.naver.com` 허용 + 키는 환경 변수(`.env` 대신)로 넣음.
- ⚠️ **클라우드 세션에서는 Supabase Postgres(5432/6543) 직접 연결 불가** (HTTPS 프록시만 통과). 백필·일일 배치는 GitHub Actions `daily-batch` 수동 실행(job=backfill, years, limit)으로 돌림.
- ✅ **Supabase 프로젝트 `dartnalysis` (ref `ojmfbdyxxzryuyehblvt`, 서울 ap-northeast-2)** 생성·migrations 0001~0003 적용 (2026-10-02, Supabase 커넥터). 시험용 빈 테이블 `_probe`가 RLS 잠금 상태로 남아 있음 — 대시보드에서 삭제 가능. DB 비밀번호·`SUPABASE_DB_URL`은 사용자만 보관.
- ⚠️ **공공데이터포털(apis.data.go.kr)은 해외 IP 차단:** GitHub Actions(미국)는 연결 시간 초과, 클라우드 세션은 간헐 끊김, Supabase 서울은 정상. → Edge Function `datagokr-relay`(서울 고정, `x-region: ap-northeast-2`)가 중계. 중계 비밀값은 DB Vault에 자동 생성(migrations/0004, `public.datagokr_relay_secret()` — service role만 실행). 파이프라인은 `SUPABASE_DB_URL`에서 프로젝트 ref·비밀값을 찾아 자동으로 중계 경유(`jobs/common.make_datagokr`), 없으면 서비스키로 직접 접속. 공공데이터포털 서비스키는 Supabase Edge Function secrets(`DATAGOKR_SERVICE_KEY`)에만 — GitHub에는 필요 없음.
- ⚠️ `web/lib/data/supabase.ts`와 Edge Function은 실제 Supabase에 붙여 테스트한 적 없음.

## 다음 할 일 (로드맵)

1. API 키 발급 → `.env` → `check_apis`로 실제 응답 확인·클라이언트 보정
2. Supabase 프로젝트 → migrations 실행 → `backfill --years 1 --limit 20` 시험 → 전체 백필
3. `DATA_SOURCE=supabase`로 웹 연결 확인
4. Edge Function 배포 + `cron.sql` → 실시간 마커 확인
5. GitHub Secrets 등록 → 일일 배치 확인 → Vercel 배포 (Root Directory = `web`)
6. 미정 사항: 서비스 이름, 투자 테마 목록·종목 매핑(시총 상위 약 200개 수동 태깅 → `companies.themes`), 초소형주 기준(`MICROCAP_THRESHOLD_KRW`), 주목할 공시 임계값(`NOTABLE_*`)
7. v2 후보: 코스닥150, 스크리너, DCF·역DCF, 몬테카를로 DCF, 리포트 PDF 내보내기
