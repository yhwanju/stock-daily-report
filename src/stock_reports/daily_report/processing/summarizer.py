from __future__ import annotations

import re

from stock_reports.daily_report.models import NewsArticle


class ArticleSummarizer:
    def summarize(
        self,
        articles: list[NewsArticle],
        preferred_lines: int = 3,
        max_lines: int = 5,
    ) -> list[NewsArticle]:
        for article in articles:
            article.title = _compact_text(article.title, limit=88)
            article.summary = "\n".join(
                self.summarize_one(
                    article,
                    preferred_lines=preferred_lines,
                    max_lines=max_lines,
                )
            )
        return articles

    def summarize_one(
        self,
        article: NewsArticle,
        preferred_lines: int = 3,
        max_lines: int = 5,
    ) -> list[str]:
        preferred_lines = max(1, min(preferred_lines, max_lines))
        source_lines = _split_sentences(article.summary)
        first_line = _first_useful_line(source_lines, article.title)
        themes = " / ".join(article.themes[:4]) if article.themes else "시장 일반"

        lines = [
            _compact_text(first_line, limit=118),
            _compact_text(f"{themes} 관련 자금 흐름과 업종 수급에 영향 가능.", limit=118),
            _compact_text(_impact_context(article.impact_score), limit=118),
        ]

        if len(article.url.splitlines()) >= 2 and len(lines) < max_lines:
            lines.append("비슷한 흐름의 복수 기사가 병합되어 테마 지속성 확인 필요.")

        return lines[:preferred_lines] if len(lines) >= preferred_lines else lines[:max_lines]


def _first_useful_line(lines: list[str], title: str) -> str:
    normalized_title = _normalize(title)
    for line in lines:
        normalized_line = _normalize(line)
        if normalized_line and normalized_line != normalized_title:
            return line
    return title


def _split_sentences(value: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return []

    parts = re.split(r"(?<=[.!?。])\s+| / |\n+", cleaned)
    return [part.strip(" -") for part in parts if part.strip(" -")]


def _impact_context(score: int) -> str:
    if score >= 5:
        return "시장 방향성까지 흔들 수 있는 재료라 장 초반 지수·선물 반응 확인 필요."
    if score == 4:
        return "산업·테마 전체로 확산될 수 있어 관련 대장주와 후속 뉴스 점검 필요."
    if score == 3:
        return "단기 테마성 매수세 유입 가능성이 있어 거래대금 증가 여부 확인 필요."
    if score == 2:
        return "특정 종목 또는 제한된 업종 중심의 영향으로 선별 접근 필요."
    return "현재 기준 시장 영향은 제한적이며 후속 확인이 필요."


def _compact_text(value: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.lower())
