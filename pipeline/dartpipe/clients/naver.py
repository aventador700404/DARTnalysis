"""네이버 검색 API (뉴스)."""

from __future__ import annotations

import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

from .http import Throttle, UsageMeter, make_session

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
_TAG = re.compile(r"<[^>]+>")


class NaverClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        session: requests.Session | None = None,
        usage: UsageMeter | None = None,
        min_interval: float = 0.1,
    ):
        self.session = session or make_session()
        self.session.headers.update({"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret})
        self.usage = usage or UsageMeter()
        self.throttle = Throttle(min_interval)

    def search_news(self, query: str, display: int = 10, sort: str = "date") -> list[dict]:
        self.usage.hit("naver")
        self.throttle.wait()
        resp = self.session.get(NEWS_URL, params={"query": query, "display": display, "sort": sort}, timeout=20)
        resp.raise_for_status()
        return [clean_news_item(it) for it in resp.json().get("items", [])]


def clean_text(s: str) -> str:
    return html.unescape(_TAG.sub("", s or "")).strip()


def clean_news_item(item: dict) -> dict:
    published: datetime | None
    try:
        published = parsedate_to_datetime(item.get("pubDate", ""))
    except (TypeError, ValueError):
        published = None
    return {
        "title": clean_text(item.get("title", "")),
        "summary": clean_text(item.get("description", "")),
        "url": item.get("originallink") or item.get("link"),
        "published_at": published.isoformat() if published else None,
    }
