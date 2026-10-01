"""DARTanalysis 데이터 파이프라인.

- clients/   : 외부 API 호출 (OpenDART, 공공데이터포털, 네이버)
- classify   : 공시 제목 → 유형 분류
- financials : 분·반기 누적 재무 → 분기별 값으로 변환
- event_study: 공시 후 초과수익률과 유형별 통계
- impact     : 공시 → 재무 영향 (희석률 등)
- valuation  : PER·PBR·ROE와 밴드 위치
- health     : 종목 건강검진 점수 (업종 내 백분위)
- benchmark  : 코스피 동일가중 평균 지수
- jobs/      : 백필·일일 배치 실행 스크립트
- mock/      : 가상 기업 샘플 데이터 생성기 (웹 데모용)
"""
