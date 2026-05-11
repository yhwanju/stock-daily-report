from __future__ import annotations

from collections import Counter

from stock_reports.daily_report.models import NewsArticle

WATCH_THEMES = (
    "AI반도체",
    "HBM",
    "전력설비",
    "구리/전력인프라",
    "원전",
    "ESS",
    "우주항공",
    "방산",
    "조선",
    "로봇",
)

CHANGE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("목표가 상향", ("목표가 상향", "target price raised", "tp 상향")),
    ("투자의견 상향", ("투자의견 상향", "상향 조정", "upgrade")),
    ("신규 커버리지", ("신규 커버", "커버리지 개시", "initiation of coverage")),
    ("산업 전망 상향", ("업황 개선", "산업 전망 상향", "outlook raised")),
    ("실적 추정 상향", ("실적 추정 상향", "earnings estimate raised", "추정치 상향")),
)

THEME_SURGE_THRESHOLD = 3


def select_research_updates(articles: list[NewsArticle], max_items: int = 5) -> list[NewsArticle]:
    matches: list[NewsArticle] = []
    for article in articles:
        text = f"{article.title} {article.summary}".lower()
        if any(keyword.lower() in text for _, keywords in CHANGE_RULES for keyword in keywords):
            if any(theme in WATCH_THEMES for theme in article.themes):
                matches.append(article)

    if len(matches) >= max_items:
        return _dedupe(matches)[:max_items]

    surge_themes = _surge_themes(articles)
    for article in articles:
        if article in matches:
            continue
        if not any(theme in surge_themes for theme in article.themes):
            continue
        if not any(theme in WATCH_THEMES for theme in article.themes):
            continue
        matches.append(article)
        if len(matches) >= max_items:
            break

    return _dedupe(matches)[:max_items]


def build_research_update_text(articles: list[NewsArticle]) -> str | None:
    if not articles:
        return None

    by_theme: dict[str, list[NewsArticle]] = {}
    for article in articles:
        theme = next((t for t in article.themes if t in WATCH_THEMES), "기타")
        by_theme.setdefault(theme, []).append(article)

    lines = ["📈 RESEARCH UPDATE 07:50", ""]
    for theme, grouped in by_theme.items():
        lines.append(f"[{theme}]")
        for article in grouped[:2]:
            lines.append(f"- {article.source}: {article.title}")
        lines.append("")
    return "\n".join(lines).strip()


def _surge_themes(articles: list[NewsArticle]) -> set[str]:
    counts: Counter[str] = Counter()
    for article in articles:
        for theme in article.themes:
            if theme in WATCH_THEMES:
                counts[theme] += 1
    return {theme for theme, count in counts.items() if count >= THEME_SURGE_THRESHOLD}


def _dedupe(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    result: list[NewsArticle] = []
    for article in articles:
        key = article.url.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result
