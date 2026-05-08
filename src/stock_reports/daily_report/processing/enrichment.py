from stock_reports.daily_report.models import NewsArticle
from stock_reports.daily_report.processing.summarizer import ArticleSummarizer


def enrich_article_cards(articles: list[NewsArticle]) -> list[NewsArticle]:
    return ArticleSummarizer().summarize(articles)
