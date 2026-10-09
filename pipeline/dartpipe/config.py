"""환경변수와 분석 파라미터를 한곳에서 관리."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    dart_api_key: str | None
    datagokr_service_key: str | None
    datagokr_relay_url: str | None
    datagokr_relay_secret: str | None
    naver_client_id: str | None
    naver_client_secret: str | None
    supabase_db_url: str | None
    dart_daily_budget: int


def get_settings() -> Settings:
    return Settings(
        dart_api_key=os.getenv("DART_API_KEY") or None,
        datagokr_service_key=(os.getenv("DATAGOKR_SERVICE_KEY") or "").strip() or None,  # 붙여넣기 공백 제거
        # 해외 실행(GitHub Actions)에서는 서울 중계를 거쳐야 함 → supabase/functions/datagokr-relay
        datagokr_relay_url=os.getenv("DATAGOKR_RELAY_URL") or None,
        datagokr_relay_secret=os.getenv("DATAGOKR_RELAY_SECRET") or None,
        naver_client_id=os.getenv("NAVER_CLIENT_ID") or None,
        naver_client_secret=os.getenv("NAVER_CLIENT_SECRET") or None,
        supabase_db_url=os.getenv("SUPABASE_DB_URL") or None,
        dart_daily_budget=int(os.getenv("DART_DAILY_BUDGET", "18000")),
    )


def require(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(
            f"환경변수 {name} 가 비어 있습니다. 저장소 루트의 .env.example 을 .env 로 복사해 채워주세요."
        )
    return value


# ── 분석 파라미터 (명세서 4장) ─────────────────────────────────
# 바꾸고 싶으면 여기만 수정하면 됩니다.

#: 공시 후 수익률 측정 구간 (거래일). 기준일을 1일째로 셈.
EVENT_HORIZONS = (5, 20)

#: 장 마감 시각 (KST). 이 시각 이후 처음 발견한 공시는 다음 거래일이 기준일.
MARKET_CLOSE_HHMM = "15:30"

#: 유형별 통계를 보여줄 최소 표본 수 (미만이면 숨김)
MIN_SAMPLE = 5

#: 평균 계산 전 상·하위 잘라낼 비율
WINSOR_PCT = 0.01

#: 측정 구간 안에서 상장주식 수가 이 비율 이상 바뀌면(액면분할·병합 등) 제외
SHARE_JUMP_EXCLUDE = 0.20

#: 시가총액이 이 값(원) 미만인 종목은 공시 통계에서 제외 (초소형주) — 명세서 미정 사항, 임시값
MICROCAP_THRESHOLD_KRW = 50_000_000_000

#: 건강검진: 업종 안 회사 수가 이보다 적으면 코스피 전체 기준으로 백분위 계산
MIN_PEERS_FOR_SECTOR_PERCENTILE = 5

#: "주목할 공시" 기준 — 명세서 미정 사항, 임시값
NOTABLE_DILUTION_PCT = 5.0  # 유상증자·전환사채 희석률 (%) 이상
NOTABLE_BUYBACK_MCAP_PCT = 1.0  # 자사주 취득 금액이 시가총액의 (%) 이상
NOTABLE_OWNERSHIP_PP = 1.0  # 지분율 변동 (%p) 이상
