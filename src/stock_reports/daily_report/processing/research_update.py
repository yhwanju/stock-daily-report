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
        market_label = _market_label(grouped)
        lines.append(f"[{_theme_label(theme)} | {market_label}]")
        for article in grouped[:2]:
            lines.extend(_brief_lines(article, theme))
        lines.append("")
    return "\n".join(lines).strip()


def _brief_lines(article: NewsArticle, theme: str) -> list[str]:
    core = _core_message(article, theme)
    market = _market_impact(article, theme)
    watch = _watchpoint(article, theme)
    source = _source_hint(article)
    return [
        f"- {core}",
        f"  · {market}",
        f"  · {watch}{source}",
    ]


def _core_message(article: NewsArticle, theme: str) -> str:
    text = f"{article.title} {article.summary}".lower()
    if any(token in text for token in ("jim cramer", "opinion", "commentary")):
        return "개별 의견 성격의 코멘트가 중심인 리포트입니다."
    if any(token in text for token in ("goldman", "reuters", "institutional", "brokerage")):
        return f"기관 시각에서 {_theme_label(theme)} 관련 전망 업데이트가 제시됐습니다."
    if any(token in text for token in ("ai", "hbm", "data center", "semiconductor", "tsmc")):
        return "빅테크 AI 투자와 데이터센터 수요 기대가 이어지고 있습니다."
    if any(token in text for token in ("power", "grid", "infrastructure", "전력")):
        return "전력망·인프라 투자 확대 시각이 재확인됐습니다."
    if any(token in text for token in ("earnings", "guidance", "estimate")):
        return "실적 전망 변화가 반영된 리포트입니다."
    return "관련 테마에 대한 추가 해석이 나온 리포트입니다."


def _market_impact(article: NewsArticle, theme: str) -> str:
    text = f"{article.title} {article.summary}".lower()
    if any(token in text for token in ("jim cramer", "opinion", "commentary")):
        return "개별 의견 성격이 강해 시장 전체 영향은 제한적일 수 있습니다."
    if any(token in text for token in ("downgrade", "cut", "둔화", "slowdown")):
        return f"{_theme_label(theme)} 관련 종목 변동성 확대 가능성."
    if any(token in text for token in ("upgrade", "raised", "outlook", "상향")):
        return f"{_theme_label(theme)} 관련 종목 투자심리 개선 가능성."
    return f"{_theme_label(theme)} 관련 매수세 유입 여부 확인 필요."


def _watchpoint(article: NewsArticle, theme: str) -> str:
    text = f"{article.title} {article.summary}".lower()
    if "ai" in text or "hbm" in text or "semiconductor" in text:
        return "AI반도체·HBM·전력설비 강세 흐름 지속 여부 체크 필요."
    if "ess" in text or "battery storage" in text:
        return "ESS·전력인프라 관련 종목 관심 유지 가능성."
    if "power" in text or "grid" in text or "infrastructure" in text:
        return "전력설비·전력인프라 관련 종목 관심 유지 가능성."
    return f"{_theme_label(theme)} 관련 종목 관심 유지 가능성."


def _source_hint(article: NewsArticle) -> str:
    short_title = article.title.strip()
    if len(short_title) > 48:
        short_title = short_title[:47].rstrip() + "…"
    return f" (참고: {article.source} | {short_title})"


def _market_label(articles: list[NewsArticle]) -> str:
    if any(article.market == "overseas" for article in articles):
        return "해외"
    return "국내"


def _theme_label(theme: str) -> str:
    if theme == "구리/전력인프라":
        return "전력인프라"
    return theme


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
