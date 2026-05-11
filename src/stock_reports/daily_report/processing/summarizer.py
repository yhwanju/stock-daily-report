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
            article.title = _normalize_title(article.title, limit=110)
            article.summary = "\n".join(
                self.summarize_one(
                    article,
                    preferred_lines=min(preferred_lines, 3),
                    max_lines=min(max_lines, 3),
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
        themes = [_theme_label(theme) for theme in article.themes[:2]] or ["시장 전반"]
        event_line = _compact_text(_event_line(article), limit=82)
        market_line = _compact_text(_market_impact_line(article), limit=82)
        theme_line = _compact_text(_theme_action_line(themes, article), limit=82)
        lines = [event_line, market_line, theme_line]
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


def _event_line(article: NewsArticle) -> str:
    text = f"{article.title} {article.summary}".lower()
    if any(token in text for token in ("실적", "earnings", "guidance", "surprise")):
        return "실적 기대감이 반영되며 관련 업종 투자심리 개선 가능성."
    if any(token in text for token in ("ai", "hbm", "semiconductor", "반도체")):
        return "AI 투자 확대 기대가 이어지며 반도체·전력인프라 테마 관심 지속."
    if any(token in text for token in ("jim cramer", "cnbc", "opinion", "commentary")):
        return "개별 종목 코멘트 성격이 강해 시장 전체 영향은 제한적."
    if any(token in text for token in ("금리", "환율", "dxy", "yield", "달러")):
        return "금리·달러 흐름에 따라 성장주 투자심리 변화 가능성."
    if any(token in text for token in ("구조조정", "layoff", "restructuring")):
        return "구조조정 이슈로 관련 종목 변동성 확대 가능성."
    return "핵심 재료 확인 전까지 시장 영향은 제한적일 수 있음."


def _market_impact_line(article: NewsArticle) -> str:
    score = article.impact_score
    if score >= 5:
        return "지수 민감 업종 중심으로 단기 매수세 유입 여부 확인 필요."
    if score == 4:
        return "관련 업종 투자심리 개선 가능성에 무게를 둘 수 있습니다."
    if score == 3:
        return "단기 매수세 유입 여부 확인 필요."
    if score == 2:
        return "시장 영향은 제한적일 수 있음."
    return "시장 전체보다 개별 이슈 성격에 가깝습니다."


def _theme_action_line(themes: list[str], article: NewsArticle) -> str:
    focus = "·".join(themes[:2])
    context = _context_phrase(themes=focus, score=article.impact_score, article=article)
    return context


def _context_phrase(themes: str, score: int, article: NewsArticle) -> str:
    text = f"{article.title} {article.summary}".lower()
    if any(token in text for token in ("실적", "earnings", "surprise", "가이던스 상향")):
        return f"{themes} 관련 종목 투자심리 개선 가능성."
    if any(token in text for token in ("구조조정", "restructuring", "감원", "layoff")):
        return f"{themes} 관련 종목 변동성 확대 가능성."
    if any(token in text for token in ("업황 둔화", "demand slowdown", "수요 둔화", "침체")):
        return f"{themes} 관련 종목 변동성 확대 가능성."
    if any(token in text for token in ("금리 부담", "고금리", "higher rates", "yield spike")):
        return f"{themes} 관련 매수세 유입 여부 확인 필요."

    # 기본 문장: 금지 표현(자금 흐름/업종 수급/영향 가능) 미사용
    if score >= 5:
        return f"{themes} 관련 매수세 유입 여부 확인 필요."
    if score == 4:
        return f"{themes} 관련 강세 흐름 이어질 가능성."
    if score == 3:
        return f"{themes} 관련 종목 투자심리 개선 가능성."
    return f"{themes} 관련 종목 변동성 확대 가능성."


def _compact_text(value: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.lower())


def _normalize_title(title: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip(" -|")
    cleaned = re.sub(r"\s*[-|]\s*(analysis|opinion|live updates?)$", "", cleaned, flags=re.IGNORECASE)
    return _compact_text(cleaned, limit=limit)


def _theme_label(theme: str) -> str:
    labels = {
        "금리/FOMC": "금리 민감주",
        "CPI/물가": "소비재·유통",
        "환율/달러": "수출주·원자재",
        "외국인 수급": "대형주",
        "AI반도체": "AI반도체",
        "HBM": "메모리반도체",
        "전력설비": "전력설비",
        "원전": "원전",
        "ESS": "ESS",
        "우주항공": "우주항공",
        "방산": "방산",
        "유가": "정유·화학",
        "구리/전력인프라": "전력인프라",
        "조선": "조선",
        "2차전지": "2차전지",
        "자동차": "자동차·부품",
        "바이오": "바이오",
        "로봇": "로봇",
        "정부 정책": "정책 수혜주",
        "대형 수주": "수주 모멘텀",
        "실적": "실적주",
        "가상자산/위험선호": "증권·성장주",
    }
    return labels.get(theme, theme)
