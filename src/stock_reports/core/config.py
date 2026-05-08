from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class ReportConfig:
    title: str
    timezone: str
    schedule_time: str
    max_articles: int
    recommended_min_articles: int
    recommended_max_articles: int
    min_impact_score: int
    duplicate_threshold: float


@dataclass(frozen=True)
class TickerConfig:
    name: str
    symbol: str
    category: str
    scale: float = 1.0


@dataclass(frozen=True)
class NewsSourceConfig:
    name: str
    market: str
    url: str
    provider: str = "generic_rss"
    method: str = "rss"
    enabled: bool = True


@dataclass(frozen=True)
class DiscordConfig:
    webhook_url: str | None


@dataclass(frozen=True)
class AppConfig:
    report: ReportConfig
    tickers: list[TickerConfig]
    news_sources: list[NewsSourceConfig]
    discord: DiscordConfig


def load_app_config(config_path: Path) -> AppConfig:
    load_dotenv()

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    report_raw = raw.get("report", {})
    ticker_raw = raw.get("market_tickers", {})
    source_raw = raw.get("news_sources", [])

    tickers: list[TickerConfig] = []
    for category, values in ticker_raw.items():
        for name, item in values.items():
            tickers.append(
                TickerConfig(
                    name=name,
                    symbol=str(item["symbol"]),
                    category=category,
                    scale=float(item.get("scale", 1.0)),
                )
            )

    sources = [
        NewsSourceConfig(
            name=str(item["name"]),
            market=str(item["market"]),
            url=str(item["url"]),
            provider=str(item.get("provider", item.get("type", "generic_rss"))),
            method=str(item.get("method", "rss")),
            enabled=bool(item.get("enabled", True)),
        )
        for item in source_raw
        if bool(item.get("enabled", True))
    ]

    return AppConfig(
        report=ReportConfig(
            title=str(report_raw.get("title", "투자 영향도 데일리 리포트")),
            timezone=str(report_raw.get("timezone", "Asia/Seoul")),
            schedule_time=str(report_raw.get("schedule_time", "07:45")),
            max_articles=int(report_raw.get("max_articles", 10)),
            recommended_min_articles=int(report_raw.get("recommended_min_articles", 5)),
            recommended_max_articles=int(report_raw.get("recommended_max_articles", 7)),
            min_impact_score=int(report_raw.get("min_impact_score", 2)),
            duplicate_threshold=float(report_raw.get("duplicate_threshold", 0.72)),
        ),
        tickers=tickers,
        news_sources=sources,
        discord=DiscordConfig(webhook_url=_optional_env("DISCORD_WEBHOOK_URL")),
    )


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()
