"""공통 HTTP 세션: 재시도, 호출 간격, 호출 수 집계."""

from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session(retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))  # 동시 요청용
    session.headers["User-Agent"] = "DARTanalysis/0.1 (+https://github.com/aventador700404/DARTanalysis)"
    return session


@dataclass
class UsageMeter:
    """API별 호출 수를 세고, 하루 예산을 넘으면 멈춘다 (api_usage 테이블로 저장)."""

    budgets: dict[str, int] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def hit(self, api: str) -> None:
        with self._lock:  # 여러 스레드가 동시에 불러도 예산을 넘지 않게
            budget = self.budgets.get(api)
            if budget is not None and self.counts[api] >= budget:
                raise BudgetExceeded(api, budget)
            self.counts[api] += 1

    def as_rows(self, day: str) -> list[dict]:
        return [{"day": day, "api": api, "calls": n} for api, n in self.counts.items()]


class BudgetExceeded(RuntimeError):
    def __init__(self, api: str, budget: int):
        super().__init__(f"{api} 하루 호출 예산({budget:,}건)에 도달해 중단합니다. 내일 다시 실행하면 이어서 진행됩니다.")
        self.api = api
        self.budget = budget


class Throttle:
    """연속 호출 사이 최소 간격 (서버에 몰아서 부르지 않기)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """동시 요청이어도 '출발' 간격은 min_interval 이상 (응답 대기는 겹쳐도 됨)."""
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self.min_interval
        if start > now:
            time.sleep(start - now)
