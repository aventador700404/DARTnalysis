"""DB 읽기·쓰기 (Supabase Postgres에 직접 연결).

REST API는 한 번에 1,000행씩만 읽혀서 수십만 행의 주가를 읽기엔 느리다.
그래서 배치 작업은 Postgres 연결 문자열(SUPABASE_DB_URL)로 직접 읽고 쓴다.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from typing import Iterable, Protocol

import pandas as pd

#: 테이블 → 충돌 기준 컬럼 (upsert 키). supabase/migrations 의 PRIMARY KEY와 같아야 함.
KEYS: dict[str, tuple[str, ...]] = {
    "companies": ("code",),
    "prices_daily": ("code", "date"),
    "index_daily": ("date",),
    "financials": ("code", "year", "quarter"),
    "annual_facts": ("code", "year"),
    "disclosures": ("rcept_no",),
    "disclosure_impacts": ("rcept_no",),
    "disclosure_stats": ("group_key", "horizon", "benchmark"),
    "scores": ("code",),
    "valuation": ("code",),
    "valuation_history": ("code", "date"),
    "news": ("url",),
    "api_usage": ("day", "api"),
}
JSON_COLUMNS = {"detail", "impact", "metric_scores", "basis", "themes_json"}

#: 이미 있으면 덮어쓰지 않는 테이블 (처음 발견한 시각 보존)
INSERT_ONLY = {"disclosures", "news"}


class Store(Protocol):
    def upsert(self, table: str, rows: list[dict], update_columns: Iterable[str] | None = None) -> int: ...

    def read_df(self, sql: str, params: dict | None = None) -> pd.DataFrame: ...

    def set_details(self, rows: list[dict]) -> None: ...


class PgStore:
    def __init__(self, dsn: str):
        import psycopg  # 실제 DB를 쓸 때만 필요

        self._psycopg = psycopg
        self.conn = psycopg.connect(dsn, autocommit=True)
        self._lock = threading.RLock()  # 여러 스레드가 한 연결을 쓸 때 한 번에 하나씩

    def read_df(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        with self._lock, self.conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c.name for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)

    def upsert(self, table: str, rows: list[dict], update_columns: Iterable[str] | None = None, chunk: int = 2000) -> int:
        if not rows:
            return 0
        from psycopg import sql
        from psycopg.types.json import Jsonb

        cols = list(rows[0].keys())
        keys = KEYS[table]
        updates = [c for c in (update_columns or cols) if c not in keys]
        conflict = (
            sql.SQL("DO NOTHING")
            if table in INSERT_ONLY or not updates
            else sql.SQL("DO UPDATE SET ") + sql.SQL(", ").join(sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in updates)
        )
        stmt = sql.SQL("INSERT INTO {t} ({cols}) VALUES ({vals}) ON CONFLICT ({keys}) ").format(
            t=sql.Identifier(table),
            cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
            vals=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
            keys=sql.SQL(", ").join(map(sql.Identifier, keys)),
        ) + conflict

        def adapt(v, col):
            if col in JSON_COLUMNS and v is not None:
                return Jsonb(v)
            return v

        total = 0
        with self._lock, self.conn.cursor() as cur:
            for i in range(0, len(rows), chunk):
                batch = [tuple(adapt(r.get(c), c) for c in cols) for r in rows[i : i + chunk]]
                cur.executemany(stmt, batch)
                total += len(batch)
        return total

    def set_details(self, rows: list[dict]) -> None:
        """disclosures는 insert-only라서 상세(detail)만 따로 갱신."""
        from psycopg.types.json import Jsonb

        with self._lock, self.conn.cursor() as cur:
            cur.executemany("UPDATE disclosures SET detail = %s WHERE rcept_no = %s", [(Jsonb(r["detail"]), r["rcept_no"]) for r in rows])


class MemoryStore:
    """테스트용: 테이블을 dict로 보관."""

    def __init__(self):
        self.tables: dict[str, dict[tuple, dict]] = defaultdict(dict)

    def upsert(self, table: str, rows: list[dict], update_columns: Iterable[str] | None = None) -> int:
        keys = KEYS[table]
        for r in rows:
            k = tuple(r[c] for c in keys)
            if table in INSERT_ONLY and k in self.tables[table]:
                continue
            merged = {**self.tables[table].get(k, {}), **json.loads(json.dumps(r, default=str))}
            self.tables[table][k] = merged
        return len(rows)

    def set_details(self, rows: list[dict]) -> None:
        for r in rows:
            if (r["rcept_no"],) in self.tables["disclosures"]:
                self.tables["disclosures"][(r["rcept_no"],)]["detail"] = r["detail"]

    def rows(self, table: str) -> list[dict]:
        return list(self.tables[table].values())

    def read_df(self, sql: str, params: dict | None = None) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError("MemoryStore는 SQL을 지원하지 않습니다")
