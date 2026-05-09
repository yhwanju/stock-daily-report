from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MarketDataPoint:
    name: str
    category: str
    value: float | None
    change_pct: float | None
    symbol: str


@dataclass
class MarketSnapshot:
    captured_at: datetime
    points: list[MarketDataPoint]
    summary_lines: list[str]


@dataclass
class NewsArticle:
    title: str
    summary: str
    url: str
    source: str
    market: str
    published_at: datetime | None = None
    source_url: str | None = None
    themes: list[str] = field(default_factory=list)
    impact_score: int = 1

    def __post_init__(self) -> None:
        if self.source_url is None:
            self.source_url = self.url


@dataclass
class ThemeScore:
    name: str
    score: int


@dataclass
class DailyReport:
    title: str
    generated_at: datetime
    market_snapshot: MarketSnapshot
    theme_scores: list[ThemeScore]
    domestic_articles: list[NewsArticle]
    overseas_articles: list[NewsArticle]
