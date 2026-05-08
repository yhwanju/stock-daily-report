from __future__ import annotations

import requests

from stock_reports.core.config import NewsSourceConfig
from stock_reports.daily_report.models import NewsArticle
from stock_reports.daily_report.data_sources.news_sources import build_news_source_client, unique_articles


class NewsCollector:
    def __init__(self, max_items_per_source: int = 25) -> None:
        self.max_items_per_source = max_items_per_source

    def collect(self, sources: list[NewsSourceConfig]) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        for source in sources:
            articles.extend(self._collect_source(source))
        return unique_articles(articles)

    def _collect_source(self, source: NewsSourceConfig) -> list[NewsArticle]:
        try:
            client = build_news_source_client(source, self.max_items_per_source)
            return client.fetch()
        except requests.RequestException:
            return []
        except Exception:
            return []
