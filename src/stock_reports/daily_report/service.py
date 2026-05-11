from __future__ import annotations

from datetime import datetime
from pathlib import Path

from stock_reports.core.config import AppConfig
from stock_reports.daily_report.data_sources.market_data import MarketDataCollector
from stock_reports.daily_report.data_sources.news import NewsCollector
from stock_reports.daily_report.models import DailyReport, NewsArticle
from stock_reports.daily_report.processing.deduplication import merge_similar_articles
from stock_reports.daily_report.processing.scoring import ImpactScorer, select_report_articles
from stock_reports.daily_report.processing.research_update import (
    build_research_update_text,
    select_research_updates,
)
from stock_reports.daily_report.processing.summarizer import ArticleSummarizer
from stock_reports.daily_report.processing.theme_classifier import ThemeClassifier
from stock_reports.daily_report.renderers.card_news import CardNewsRenderer, build_discord_card_summary
from stock_reports.daily_report.report_builder import DailyReportBuilder
from stock_reports.daily_report.sample_data import sample_market_snapshot, sample_news_articles
from stock_reports.integrations.discord import DiscordWebhookClient


class DailyReportService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.market_collector = MarketDataCollector()
        self.news_collector = NewsCollector()
        self.theme_classifier = ThemeClassifier()
        self.impact_scorer = ImpactScorer()
        self.summarizer = ArticleSummarizer()
        self.report_builder = DailyReportBuilder()
        self.card_news_renderer = CardNewsRenderer()

    def run_once(
        self,
        send: bool = False,
        use_sample_data: bool = False,
        fallback_to_sample: bool = False,
        template: str = "markdown",
        output_dir: Path | None = None,
    ) -> str:
        report = self.build_report(
            use_sample_data=use_sample_data,
            fallback_to_sample=fallback_to_sample,
        )
        report_text = self.report_builder.build(report)
        image_paths: list[Path] = []

        if template == "card_news":
            target_dir = output_dir or Path.cwd() / "output"
            image_paths = self.card_news_renderer.render_pngs(report, target_dir)
        elif template != "markdown":
            raise ValueError(f"Unsupported report template: {template}")

        if send:
            if not self.config.discord.webhook_url:
                raise RuntimeError("DISCORD_WEBHOOK_URL is not configured.")

            client = DiscordWebhookClient(self.config.discord.webhook_url)
            if image_paths:
                card_message = "\n\n".join(
                    [
                        build_discord_card_summary(report, image_paths),
                        self.report_builder.build_article_link_list(report),
                    ]
                )
                client.send_text_with_files(
                    card_message,
                    image_paths,
                )
            else:
                client.send_text(report_text)

        if image_paths:
            paths = "\n".join(str(path) for path in image_paths)
            return f"{report_text}\n\n[card_news PNG]\n{paths}"

        return report_text

    def run_research_update(self, send: bool = False) -> str | None:
        articles = self.news_collector.collect(self.config.news_sources)
        if not articles:
            return None
        articles = self.theme_classifier.classify(articles)
        articles = self.impact_scorer.score(articles)
        selected = select_research_updates(articles, max_items=5)
        message = build_research_update_text(selected)
        if not message:
            return None
        if send:
            if not self.config.discord.webhook_url:
                raise RuntimeError("DISCORD_WEBHOOK_URL is not configured.")
            DiscordWebhookClient(self.config.discord.webhook_url).send_text(message)
        return message

    def build_report(
        self,
        use_sample_data: bool = False,
        fallback_to_sample: bool = False,
    ) -> DailyReport:
        if use_sample_data:
            market_snapshot = sample_market_snapshot()
            articles = sample_news_articles()
        else:
            market_snapshot = self.market_collector.collect(self.config.tickers)
            articles = self.news_collector.collect(self.config.news_sources)

            if fallback_to_sample and _has_no_market_values(market_snapshot.points):
                market_snapshot = sample_market_snapshot()
            if fallback_to_sample and not articles:
                articles = sample_news_articles()

        articles = self.theme_classifier.classify(articles)
        articles = self.impact_scorer.score(articles)
        articles = merge_similar_articles(
            articles,
            threshold=self.config.report.duplicate_threshold,
        )
        articles = self.theme_classifier.classify(articles)
        articles = self.impact_scorer.score(articles)
        articles = select_report_articles(
            articles,
            min_impact_score=self.config.report.min_impact_score,
            recommended_max_articles=self.config.report.recommended_max_articles,
            max_articles=self.config.report.max_articles,
        )
        articles = self.summarizer.summarize(articles)

        domestic_articles = _by_market(articles, "domestic")
        overseas_articles = _by_market(articles, "overseas")

        report = DailyReport(
            title=self.config.report.title,
            generated_at=datetime.now(),
            market_snapshot=market_snapshot,
            theme_scores=self.theme_classifier.rank_themes(articles),
            domestic_articles=domestic_articles,
            overseas_articles=overseas_articles,
        )
        return report


def _by_market(articles: list[NewsArticle], market: str) -> list[NewsArticle]:
    return [article for article in articles if article.market == market]


def _has_no_market_values(points: list[object]) -> bool:
    return all(getattr(point, "value", None) is None for point in points)
