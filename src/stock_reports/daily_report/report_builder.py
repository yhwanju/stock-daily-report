from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qs, unquote, urlparse

from stock_reports.daily_report.models import DailyReport, MarketDataPoint, NewsArticle, ThemeScore


GENERIC_URL_PATHS = {
    "",
    "/",
    "/business",
    "/finance",
    "/markets",
    "/markets/",
    "/news",
    "/news/",
    "/personal-finance",
    "/personal-finance/",
}

GENERIC_URL_MARKERS = (
    "rssindex",
    "/rss",
    "/device/rss",
    "rss.html",
    "feed",
)

RELATED_URL_MARKERS = (
    "related",
    "recommended",
    "recommendation",
    "recirculation",
    "more-stories",
    "morestories",
)

URL_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "over",
    "says",
    "the",
    "to",
    "up",
    "with",
    "www",
    "com",
    "html",
    "htm",
    "rss",
    "feed",
    "http",
    "https",
    "index",
    "news",
    "article",
    "articles",
    "story",
    "stories",
    "markets",
    "market",
    "business",
    "finance",
    "latest",
    "today",
    "live",
    "updates",
    "device",
    "id",
    "amp",
    "review",
}

URL_MISMATCH_GROUPS = (
    {"mortgage", "mortgages", "refinance", "lender", "lenders", "housing", "loan", "loans"},
    {"credit", "card", "cards", "banking", "checking", "savings", "insurance", "personal"},
)


class DailyReportBuilder:
    def build(self, report: DailyReport) -> str:
        domestic_articles = _valid_link_articles(report.domestic_articles)
        overseas_articles = _valid_link_articles(report.overseas_articles)

        lines: list[str] = []
        lines.append(f"📰 {report.title}")
        lines.append(report.generated_at.strftime("%Y-%m-%d %H:%M"))
        lines.append("")
        lines.extend(self._build_today_market(report.market_snapshot.points, report.market_snapshot.summary_lines))
        lines.append("")
        lines.extend(self._build_theme_strength(report.theme_scores))
        lines.append("")
        lines.extend(self._build_section("🇰🇷 국내 증시", domestic_articles))
        lines.append("")
        lines.extend(self._build_section("🇺🇸 해외 증시", overseas_articles))
        return "\n".join(lines)

    def build_article_link_list(self, report: DailyReport) -> str:
        domestic_articles = _valid_link_articles(report.domestic_articles)
        overseas_articles = _valid_link_articles(report.overseas_articles)

        lines: list[str] = ["🔗 기사 원문 링크", ""]
        lines.extend(self._build_link_section("[국내]", domestic_articles, start_number=1))
        lines.append("")
        lines.extend(
            self._build_link_section(
                "[해외]",
                overseas_articles,
                start_number=len(domestic_articles) + 1,
            )
        )
        return "\n".join(lines).strip()

    def _build_today_market(self, points: list[MarketDataPoint], summary_lines: list[str]) -> list[str]:
        grouped = {
            "지수": ["KOSPI", "KOSDAQ", "NASDAQ", "SOX"],
            "환율/금리": ["USD/KRW", "US10Y", "DXY"],
            "원자재": ["WTI", "Gold", "Copper"],
            "리스크": ["VIX", "Bitcoin"],
        }
        by_name = {point.name: point for point in points}

        lines = ["━━━━━━━━━━━━━━━━━━", "TODAY MARKET", "━━━━━━━━━━━━━━━━━━"]
        for label, names in grouped.items():
            values = [self._format_market_point(by_name.get(name), name) for name in names]
            lines.append(f"[{label}] " + " | ".join(values))

        lines.append("")
        lines.extend(f"• {line}" for line in summary_lines[:3])
        return lines

    def _build_theme_strength(self, theme_scores: list[ThemeScore]) -> list[str]:
        if not theme_scores:
            return ["[오늘 강세 예상 테마]", "주요 테마는 뉴스 수집 후 산출됩니다."]

        lines = ["[오늘 강세 예상 테마]"]
        for theme in theme_scores:
            bar = "█" * max(1, theme.score)
            lines.append(f"{theme.name:<12} {bar}")
        return lines

    def _build_section(self, title: str, articles: list[NewsArticle]) -> list[str]:
        lines = ["━━━━━━━━━━━━━━━━━━", title, "━━━━━━━━━━━━━━━━━━"]
        if not articles:
            lines.append("투자 영향도가 높은 뉴스가 아직 선별되지 않았습니다.")
            return lines

        for article in articles:
            lines.extend(self._build_article_card(article))
            lines.append("")
        return lines

    def _build_link_section(
        self,
        title: str,
        articles: list[NewsArticle],
        start_number: int,
    ) -> list[str]:
        lines = [title]
        if not articles:
            lines.append("선별된 기사가 없습니다.")
            return lines

        for offset, article in enumerate(articles):
            url = _article_url(article)
            if not url:
                continue

            number = start_number + offset
            lines.append(f"{number}. {article.title}")
            lines.append(url)
            lines.append("")

        if lines[-1] == "":
            lines.pop()
        return lines

    def _build_article_card(self, article: NewsArticle) -> list[str]:
        summary_lines = _compact_summary(article.summary, max_lines=5)
        themes = " / ".join(article.themes) if article.themes else "시장 일반"
        stars = "★" * article.impact_score + "☆" * (5 - article.impact_score)

        lines = [
            f"[{article.title}]",
            "",
        ]
        lines.extend(summary_lines)
        lines.extend(
            [
                "",
                f"[영향 테마] {themes}",
                f"[영향 강도] {stars} ({article.impact_score}/5)",
                "[원문 기사 링크]",
                _article_url(article) or "원문 링크 없음",
            ]
        )
        return lines

    def _format_market_point(self, point: MarketDataPoint | None, fallback_name: str) -> str:
        if point is None or point.value is None:
            return f"{fallback_name} -"

        change = ""
        if point.change_pct is not None:
            sign = "+" if point.change_pct >= 0 else ""
            change = f" ({sign}{point.change_pct:.2f}%)"

        return f"{point.name} {point.value:,.2f}{change}"


def _compact_summary(summary: str, max_lines: int) -> list[str]:
    if not summary:
        return ["• 세부 내용은 원문 기사 확인 필요."]

    if "\n" in summary:
        lines = [line.strip(" •") for line in summary.splitlines() if line.strip(" •")]
    else:
        sentences = summary.replace("...", ".").split(".")
        lines = [sentence.strip() for sentence in sentences if sentence.strip()]

    if not lines:
        lines = [summary.strip()]

    return [f"• {line}" for line in lines[:max_lines]]


def _valid_link_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    valid_articles: list[NewsArticle] = []
    for article in articles:
        url = _article_url(article)
        if not url:
            continue
        article.source_url = url
        article.url = url
        valid_articles.append(article)
    return valid_articles


def _article_url(article: NewsArticle) -> str | None:
    for url in _candidate_urls(article):
        if _is_valid_article_url(article, url):
            return url
    return None


def _candidate_urls(article: NewsArticle) -> list[str]:
    candidates: list[str] = []
    source_url = getattr(article, "source_url", None)
    if source_url:
        candidates.extend(_split_urls(source_url))
    candidates.extend(_split_urls(article.url))

    result: list[str] = []
    for url in candidates:
        if url and url not in result:
            result.append(url)
    return result


def _split_urls(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _is_valid_article_url(article: NewsArticle, url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    if article.source.lower() == "sample" or parsed.netloc.lower() == "example.com":
        return True

    if _is_generic_url(parsed):
        return False

    if _is_opaque_article_url(parsed):
        return True

    url_tokens = _url_tokens(url)
    title_tokens = _text_tokens(article.title)
    summary_tokens = _text_tokens(article.summary)
    text_tokens = title_tokens | summary_tokens

    if not url_tokens or not title_tokens:
        return False

    if _has_unrelated_topic(url_tokens, text_tokens):
        return False

    title_overlap = len(title_tokens & url_tokens) / max(1, min(len(title_tokens), len(url_tokens)))
    sequence_score = SequenceMatcher(
        None,
        " ".join(sorted(title_tokens)),
        " ".join(sorted(_url_tokens(parsed.path))),
    ).ratio()

    return (title_overlap * 0.8 + sequence_score * 0.2) >= 0.12


def _is_generic_url(parsed_url: object) -> bool:
    parsed = parsed_url if hasattr(parsed_url, "path") else urlparse(str(parsed_url))
    path = (parsed.path or "").lower()
    path_and_query = unquote(f"{parsed.path} {parsed.query}").lower()
    normalized_path = path.rstrip("/") or "/"

    if normalized_path in GENERIC_URL_PATHS:
        return True
    if any(marker in path_and_query for marker in GENERIC_URL_MARKERS):
        return True
    if any(marker in path_and_query for marker in RELATED_URL_MARKERS):
        return True

    tokens = _url_tokens(parsed.geturl())
    if {"rss", "feed", "rssindex"} & tokens:
        return True

    path_parts = [part for part in normalized_path.split("/") if part]
    return len(path_parts) <= 1 and any(part in {"news", "markets", "business", "finance"} for part in path_parts)


def _is_opaque_article_url(parsed_url: object) -> bool:
    parsed = parsed_url if hasattr(parsed_url, "path") else urlparse(str(parsed_url))
    netloc = (parsed.netloc or "").lower()
    query = parse_qs(parsed.query)
    path = (parsed.path or "").lower()

    if "naver.com" in netloc and ("article_id" in query or "office_id" in query):
        return True
    if "naver.com" in netloc and "/news/" in path and re.search(r"\d{6,}", parsed.query):
        return True
    return False


def _text_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[0-9a-z가-힣]+", value.lower())
    return {token for token in tokens if len(token) >= 2 and token not in URL_STOPWORDS}


def _url_tokens(value: str) -> set[str]:
    parsed = urlparse(value)
    decoded = unquote(f"{parsed.path} {parsed.query}").lower()
    tokens = re.findall(r"[0-9a-z가-힣]+", decoded)
    return {
        token
        for token in tokens
        if len(token) >= 2 and not token.isdigit() and token not in URL_STOPWORDS
    }


def _has_unrelated_topic(url_tokens: set[str], text_tokens: set[str]) -> bool:
    for topic_tokens in URL_MISMATCH_GROUPS:
        if url_tokens & topic_tokens and not text_tokens & topic_tokens:
            return True
    return False
