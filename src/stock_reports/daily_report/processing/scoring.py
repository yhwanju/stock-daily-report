from __future__ import annotations

from stock_reports.daily_report.models import NewsArticle


THEME_WEIGHTS = {
    "금리/FOMC": 5,
    "CPI/물가": 5,
    "AI반도체": 5,
    "환율/달러": 4,
    "유가": 4,
    "구리/전력인프라": 4,
    "전력설비": 4,
    "원전": 4,
    "HBM": 4,
    "우주항공": 3,
    "방산": 3,
    "ESS": 3,
    "외국인 수급": 3,
    "정부 정책": 3,
    "대형 수주": 3,
    "실적": 3,
    "조선": 3,
    "2차전지": 3,
    "자동차": 3,
    "바이오": 2,
    "로봇": 2,
    "가상자산/위험선호": 2,
}

MARKET_DIRECTION_KEYWORDS = (
    "fomc",
    "fed",
    "연준",
    "cpi",
    "물가",
    "금리",
    "treasury",
    "미국채",
    "nvidia",
    "엔비디아",
    "nasdaq",
    "sox",
)

INDUSTRY_KEYWORDS = (
    "수주",
    "공급계약",
    "guidance",
    "가이던스",
    "surprise",
    "서프라이즈",
    "subsidy",
    "지원책",
    "tariff",
    "관세",
)


class ImpactScorer:
    def score(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        for article in articles:
            article.impact_score = self.score_one(article)
        return articles

    def score_one(self, article: NewsArticle) -> int:
        text = f"{article.title} {article.summary}".lower()
        score = max((THEME_WEIGHTS.get(theme, 1) for theme in article.themes), default=1)

        if any(keyword in text for keyword in MARKET_DIRECTION_KEYWORDS):
            score = max(score, 4)
        if any(keyword in text for keyword in INDUSTRY_KEYWORDS):
            score = max(score, 3)
        if len(article.url.splitlines()) >= 2:
            score = min(5, score + 1)

        return max(1, min(score, 5))


def select_report_articles(
    articles: list[NewsArticle],
    min_impact_score: int,
    recommended_max_articles: int,
    max_articles: int,
) -> list[NewsArticle]:
    hard_limit = max(1, max_articles)
    target_count = min(hard_limit, max(1, recommended_max_articles))
    relevant = _sort_articles(
        [article for article in articles if article.impact_score >= min_impact_score]
    )

    if len(relevant) <= target_count:
        return relevant[:hard_limit]

    selected: list[NewsArticle] = []
    base_quota = 2 if target_count >= 5 else 1

    for market in ("domestic", "overseas"):
        market_articles = [article for article in relevant if article.market == market]
        take_count = min(base_quota, len(market_articles), target_count - len(selected))
        selected.extend(market_articles[:take_count])

    selected_keys = {_article_key(article) for article in selected}
    for article in relevant:
        if len(selected) >= target_count:
            break
        key = _article_key(article)
        if key not in selected_keys:
            selected.append(article)
            selected_keys.add(key)

    return _sort_articles(selected)[:hard_limit]


def filter_relevant_articles(
    articles: list[NewsArticle],
    min_impact_score: int,
    max_articles: int,
) -> list[NewsArticle]:
    return _sort_articles(
        [article for article in articles if article.impact_score >= min_impact_score]
    )[:max_articles]


def _sort_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    return sorted(
        articles,
        key=lambda item: (item.impact_score, _published_timestamp(item)),
        reverse=True,
    )


def _published_timestamp(article: NewsArticle) -> float:
    if article.published_at is None:
        return 0.0
    return article.published_at.timestamp()


def _article_key(article: NewsArticle) -> str:
    return article.url.splitlines()[0].split("?")[0].rstrip("/")
