from __future__ import annotations

from stock_reports.daily_report.models import NewsArticle, ThemeScore
from stock_reports.daily_report.processing.scoring import (
    ImpactScorer,
    filter_relevant_articles,
    select_report_articles,
)
from stock_reports.daily_report.processing.theme_classifier import ThemeClassifier


class KeywordImpactScorer:
    def __init__(self) -> None:
        self.theme_classifier = ThemeClassifier()
        self.impact_scorer = ImpactScorer()

    def score(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        articles = self.theme_classifier.classify(articles)
        return self.impact_scorer.score(articles)

    def rank_themes(self, articles: list[NewsArticle]) -> list[ThemeScore]:
        return self.theme_classifier.rank_themes(articles)
