# DARTnalysis 코드 설명 및 AI 활용 기록

작성일: 2026-11-01  
코드 확인 기준: `725dcae19c593261d1faadde550ab3f3df1b55c9`

## 1. 프로젝트 목적과 주요 기능

DARTnalysis는 공시 시점, 이후 주가 변화, 기업의 재무정보를 함께 살펴보는 웹 대시보드다. 사용자가 종목을 검색하고 차트의 공시를 선택하면 공시 후 수익률과 재무 영향, 같은 유형의 과거 통계, 관련 정보를 확인하도록 구성돼 있다.

주요 화면은 종목 차트·공시 패널, 재무 추이, 성장성·수익성 등 5개 항목의 요약, 동종기업 비교, 홈의 공시 피드와 업종 비교다. 분석은 과거 자료의 계산·비교를 중심으로 하며, DCF·역DCF 등은 README의 후순위 항목이다.

## 2. 현재 구현 범위

저장소에는 웹 화면, Python 수집·분석 파이프라인, Postgres 스키마, 공시 수집 함수와 예약 실행 설정이 있다. 기본 화면은 가상 기업과 가상 공시를 사용한다. 실제 데이터 모드는 별도 환경 설정으로 선택한다.

현재 [README](../README.md)는 가상 데이터 기반 동작과 테스트·빌드 수행 기록을 제시하면서 실제 외부 API 실행은 아직 확인하지 않았다고 명시한다. 따라서 소스에 수집 코드가 있다는 사실과 실제 서비스에서 데이터 수집·갱신이 완료됐다는 사실은 나눠 읽어야 한다. 이 문서 작성 과정에서는 외부 API·배포·테스트를 새로 실행하지 않았다.

## 3. 데이터는 어디에서 오고 어떻게 연결되는가

| 자료 | 연결 대상 | 코드 |
|---|---|---|
| 공시, 기업 정보, 재무제표, 증자·자사주 등 상세 | OpenDART | [clients/dart.py](../pipeline/dartpipe/clients/dart.py) |
| 일별 주가, 시가총액, 주식 수, 기준 지수 | 공공데이터포털 API | [clients/datagokr.py](../pipeline/dartpipe/clients/datagokr.py) |
| 관련 뉴스 | 네이버 뉴스 검색 API, 선택적 연결 | [clients/naver.py](../pipeline/dartpipe/clients/naver.py) |

기업 정보에 종목코드와 DART 고유번호를 두고, 주가·재무·공시를 같은 회사에 연결한다. 주가는 날짜, 재무는 연도·분기, 공시는 접수번호를 기준으로 관리한다.

## 4. 수집에서 화면까지의 흐름

1. **원천 수집:** 최초 과거 자료는 `backfill`, 이후 갱신은 `daily` 작업이 담당한다. 공시 확인은 별도 Edge Function과 Cron 설정이 담당한다.
2. **자료 정리:** 회사별 재무 계정을 공통 항목으로 맞추고 누적 보고 금액을 분기별 금액으로 변환한다.
3. **분석:** 공시 유형 분류, 기준 거래일 결정, 공시 후 수익률·초과수익률, 재무 영향, 재무·밸류에이션 지표 등을 계산한다.
4. **저장:** 원천 자료와 계산 결과를 Supabase Postgres 테이블에 저장하도록 구성한다.
5. **조회:** Next.js 웹 화면이 가상 데이터 또는 Supabase 조회 결과를 같은 화면용 형식으로 받아 표시한다.
6. **갱신:** 일일 배치는 자료 갱신과 지표 재계산을 담당한다. 새 공시 전달에는 Supabase Realtime 연결 경로가 포함돼 있다.

가상 데이터 생성기도 [analyze.py](../pipeline/dartpipe/analyze.py)의 분석 함수를 사용한다. 이를 통해 화면용 숫자만 임의로 배치하는 대신 계산 흐름을 함께 확인할 수 있다. 실제 API 응답 적합성과 실제 데이터 품질 검증은 별도 작업이다.

## 5. 주요 파일의 역할

| 파일·폴더 | 담당 기능 |
|---|---|
| [web/app](../web/app) | 홈·종목·업종 비교 페이지 |
| [StockView.tsx](../web/components/stock/StockView.tsx) | 종목 화면의 차트·공시 선택·탭 상태 연결 |
| [DisclosurePanel.tsx](../web/components/stock/DisclosurePanel.tsx) | 선택한 공시의 주가 반응·재무 영향·분포 표시 |
| [web/lib/data/index.ts](../web/lib/data/index.ts) | `DATA_SOURCE` 설정에 따라 가상 데이터와 DB 조회 경로 선택 |
| [web/lib/data/supabase.ts](../web/lib/data/supabase.ts) | DB 결과를 웹 화면에서 사용할 형식으로 조회·정리 |
| [pipeline/dartpipe/jobs](../pipeline/dartpipe/jobs) | 최초 수집, 일일 갱신, API 연결 점검 작업 |
| [financials.py](../pipeline/dartpipe/financials.py) | 표준 계정 매핑과 분기 재무 변환 |
| [event_study.py](../pipeline/dartpipe/event_study.py) | 공시 기준일, 5·20거래일 수익률·초과수익률, 유형별 통계 |
| [impact.py](../pipeline/dartpipe/impact.py) | 증자·자사주 등 공시의 주식 수·금액 관련 영향 계산 |
| [valuation.py](../pipeline/dartpipe/valuation.py), [health.py](../pipeline/dartpipe/health.py) | 재무·가격 지표 및 업종 내 상대 위치 계산 |
| [analyze.py](../pipeline/dartpipe/analyze.py) | 정리된 원천 자료를 화면·DB용 결과로 변환하는 분석 연결부 |
| [store.py](../pipeline/dartpipe/store.py) | Python 배치의 Postgres 읽기·쓰기, 중복 자료 처리 |
| [supabase/migrations](../supabase/migrations) | DB 테이블·인덱스·권한 및 관련 함수 정의 |
| [poll-disclosures](../supabase/functions/poll-disclosures/index.ts), [cron.sql](../supabase/cron.sql) | 공시 수집 함수 및 실행 주기 설정 |
| [.github/workflows](../.github/workflows) | 테스트·빌드와 데이터 배치 실행 설정 |

## 6. 핵심 계산을 읽는 방법

### 공시 후 주가 변화

공시 영향을 처음 받는 거래일을 기준으로, 그 전날 종가와 5·20번째 거래일의 종가를 비교한다. 발견 시각을 알고 장중에 확인한 공시는 당일, 장 마감 후이거나 과거 공시의 시각을 모르면 다음 거래일을 기준으로 삼는다.

초과수익률은 종목 수익률에서 같은 기간 기준 지수의 수익률을 뺀 값이다. 코스피와 동일가중 기준을 함께 다룬다. 거래정지와 큰 주식 수 변화 등 비교가 어려운 구간은 제외 사유를 남긴다. 이는 공시와 이후 주가의 과거 관계를 측정하는 계산이며 인과효과의 증명은 아니다.

### 누적 재무를 분기별 값으로 바꾸기

보고서의 누적 금액을 그대로 분기 실적으로 쓰면 분기 간 비교가 왜곡된다. `financials.py`는 계정·보고서 종류에 맞춰 당분기 값 또는 누적 값의 차이를 사용한다. 예를 들어 4분기 흐름 항목은 연간 금액에서 3분기 누적 금액을 빼며, 재무상태표는 분기 말 잔액을 사용한다. 자료가 없어 계산할 수 없는 값은 비워 둔다.

### 종목 건강검진

성장성·수익성·안정성·가격·주주환원 항목을 지표별 업종 내 백분위로 정리한다. 업종의 유효 비교 기업이 적으면 코스피 전체를 사용한다. 각 항목은 별도로 보여주며 종합점수로 합산하지 않는다. 금융업은 현재 계산에서 제외돼 있다.

### 표본 수와 해석

유형별 통계에는 평균뿐 아니라 중앙값, 상승 비율, 표본 수와 분포를 담는다. 최소 표본에 못 미치면 통계를 숨긴다. 이를 통해 수치의 크기와 함께 비교에 쓰인 자료의 범위를 확인하도록 구성한다.

## 7. DB와 실행 구조를 이렇게 나눈 이유

- **회사·주가·공시·재무 분리:** 자료의 기준 시점과 갱신 주기가 서로 다르므로 기업 키로 연결하면서 각각 관리한다.
- **계산 결과 저장:** 화면 요청 때마다 전체 과거 데이터를 계산하지 않도록 배치에서 결과를 만든다.
- **Python 배치의 DB 직접 연결:** 대량 자료는 `PgStore`가 Postgres로 읽고 쓰며, 테이블별 키에 맞춰 중복 자료를 처리한다.
- **가상/실제 모드 분리:** API 키가 없어도 화면을 확인할 수 있게 하고, 실제 연결 경로는 별도 설정으로 준비한다.
- **공시와 일별 시세의 주기 분리:** 새 공시 확인과 일별 주가·재무 갱신을 서로 다른 실행 작업으로 구성한다.

DB에는 `companies`, `prices_daily`, `financials`, `disclosures` 같은 원천 테이블과 `disclosure_impacts`, `disclosure_stats`, `scores`, `valuation` 같은 결과 테이블이 있다. 자세한 키와 컬럼은 마이그레이션과 `store.py`에서 확인할 수 있다.

## 8. 개발 과정에서의 AI 활용

개발자가 정한 공시·주가·재무 연결이라는 목적과 기능 명세를 바탕으로 AI 코딩 도구를 활용해 프로젝트를 구성한 사례다. AI는 코드와 화면, 계산·수집 처리, 테스트 및 문서 작성에 활용하는 개발 도구이며, 현재 설명된 서비스의 분석 흐름은 외부 API 자료와 Python 계산으로 구성돼 있다.

개발자의 기획 판단은 어떤 정보를 함께 보여줄지, 어떤 비교 기준을 사용할지, 어느 기능부터 구현할지에 있다. 운영·분석 품질을 평가하려면 실제 API 응답과 저장 결과, 원문 공시 및 재무 수치를 대조하는 검토가 이어져야 한다. AI로 생성한 코드가 있다는 사실만으로 실제 데이터 연동 또는 분석 정확성을 확인한 것으로 간주하지 않는다.

## 9. 실행과 다음 검증

샘플 화면의 기본 실행 방법은 다음과 같다.

```bash
cd web
npm install
npm run dev
```

실제 연결은 [README](../README.md)의 API·DB·배포 절차를 따른다. [check_apis.py](../pipeline/dartpipe/jobs/check_apis.py)는 키와 응답을 점검하기 위한 코드다.

[pipeline/tests](../pipeline/tests)에는 분기 재무 변환, 공시 후 수익률, 영향·건강검진, API 처리와 DB 작업 등에 대한 테스트가 있다. 실제 API 실행, 전 종목 자료 수집, 장기 운영 및 분석 품질 검증은 소스·가상 데이터 테스트와 별도로 확인해야 한다.

요구 기능과 범위는 [Notion 기능 명세서](https://app.notion.com/p/DART-v0-1-3ea0e4c1598d814dad57f2e5176a0f15), 전체 실행 안내는 [README](../README.md)를 참고한다.
