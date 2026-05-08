from __future__ import annotations

import re
from difflib import SequenceMatcher

from stock_reports.daily_report.models import NewsArticle


FLOW_MERGE_THEMES = {
    "AI반도체",
    "HBM",
    "금리/FOMC",
    "CPI/물가",
    "환율/달러",
    "전력설비",
    "원전",
    "ESS",
    "구리/전력인프라",
    "유가",
}


def merge_similar_articles(
    articles: list[NewsArticle],
    threshold: float,
) -> list[NewsArticle]:
    merged: list[NewsArticle] = []

    for article in articles:
        duplicate = _find_duplicate(article, merged, threshold)
        if duplicate is None:
            merged.append(article)
            continue

        duplicate.title = _merge_title(duplicate, article)
        duplicate.summary = _merge_summary(duplicate.summary, article.summary)
        duplicate.url = _merge_urls(duplicate.url, article.url)
        duplicate.themes = _merge_themes(duplicate.themes, article.themes)
        duplicate.impact_score = max(duplicate.impact_score, article.impact_score)

    return merged


def _find_duplicate(
    article: NewsArticle,
    candidates: list[NewsArticle],
    threshold: float,
) -> NewsArticle | None:
    article_key = _normalize(article.title)
    for candidate in candidates:
        if article.market != candidate.market:
            continue
        candidate_key = _normalize(candidate.title)
        similarity = SequenceMatcher(None, article_key, candidate_key).ratio()
        if similarity >= threshold or _is_same_market_flow(article, candidate):
            return candidate
    return None


def _normalize(value: str) -> str:
    lowered = value.lower()
    cleaned = re.sub(r"[^0-9a-z가-힣]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_same_market_flow(article: NewsArticle, candidate: NewsArticle) -> bool:
    if not article.themes or not candidate.themes:
        return False

    shared_themes = set(article.themes) & set(candidate.themes)
    if not shared_themes:
        return False

    if max(article.impact_score, candidate.impact_score) < 4:
        return False

    if shared_themes & FLOW_MERGE_THEMES:
        return True

    article_tokens = set(_normalize(f"{article.title} {article.summary}").split())
    candidate_tokens = set(_normalize(f"{candidate.title} {candidate.summary}").split())
    if not article_tokens or not candidate_tokens:
        return False

    overlap = article_tokens & candidate_tokens
    overlap_ratio = len(overlap) / max(1, min(len(article_tokens), len(candidate_tokens)))
    return overlap_ratio >= 0.18


def _merge_title(current: NewsArticle, incoming: NewsArticle) -> str:
    if incoming.impact_score > current.impact_score:
        return incoming.title
    if len(incoming.title) < len(current.title) and current.impact_score == incoming.impact_score:
        return incoming.title
    return current.title


def _merge_summary(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming in current:
        return current
    return f"{current} / {incoming}"


def _merge_urls(current: str, incoming: str) -> str:
    urls = []
    for url in [current, incoming]:
        for part in url.split("\n"):
            if part and part not in urls:
                urls.append(part)
    return "\n".join(urls[:3])


def _merge_themes(current: list[str], incoming: list[str]) -> list[str]:
    merged = list(current)
    for theme in incoming:
        if theme not in merged:
            merged.append(theme)
    return merged
