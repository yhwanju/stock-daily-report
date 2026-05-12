from __future__ import annotations

import re
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
    ("목표가 상향", ("목표가 상향", "target price raised", "price target raised", "tp 상향")),
    ("목표가 하향", ("목표가 하향", "target price cut", "price target cut", "lowered target")),
    ("투자의견 상향", ("투자의견 상향", "상향 조정", "upgrade")),
    ("투자의견 하향", ("투자의견 하향", "하향 조정", "downgrade")),
    ("신규 커버리지", ("신규 커버", "커버리지 개시", "initiation of coverage")),
    ("산업 전망 상향", ("업황 개선", "산업 전망 상향", "outlook raised")),
    ("실적 추정 상향", ("실적 추정 상향", "earnings estimate raised", "추정치 상향")),
)

THEME_FALLBACK_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AI반도체", ("ai", "artificial intelligence", "nvidia", "semiconductor", "chip", "tsmc", "반도체")),
    ("HBM", ("hbm", "high bandwidth memory", "dram", "d램", "메모리")),
    ("전력설비", ("power", "grid", "transformer", "전력", "전선", "변압기", "송배전")),
    ("구리/전력인프라", ("copper", "구리", "power infrastructure", "전력인프라")),
    ("원전", ("nuclear", "smr", "reactor", "원전")),
    ("ESS", ("ess", "battery storage", "energy storage", "에너지저장")),
    ("우주항공", ("space", "aerospace", "satellite", "우주", "항공", "위성")),
    ("방산", ("defense", "defence", "missile", "방산", "무기", "수출 계약")),
    ("조선", ("shipbuilding", "lng carrier", "lng선", "조선", "선박")),
    ("로봇", ("robot", "robotics", "automation", "로봇", "자동화")),
)

THEME_SURGE_THRESHOLD = 3

OPINION_TOKENS = ("jim cramer", "opinion", "commentary", "column")
NEGATIVE_TOKENS = ("downgrade", "target price cut", "price target cut", "cut its rating", "하향", "둔화", "slowdown")
POSITIVE_TOKENS = ("upgrade", "raised", "outlook", "상향", "개선")


def select_research_updates(articles: list[NewsArticle], max_items: int = 5) -> list[NewsArticle]:
    matches: list[NewsArticle] = []

    for article in articles:
        text = _article_text(article)
        if _matching_change_label(text) and _article_watch_theme(article):
            matches.append(article)

    if len(matches) >= max_items:
        return _dedupe(matches)[:max_items]

    surge_themes = _surge_themes(articles)

    for article in articles:
        if article in matches:
            continue

        theme = _article_watch_theme(article)
        if theme is None:
            continue

        if theme in surge_themes:
            matches.append(article)

        if len(matches) >= max_items:
            break

    return _dedupe(matches)[:max_items]


def build_research_update_text(articles: list[NewsArticle]) -> str | None:
    if not articles:
        return None

    by_theme: dict[str, list[NewsArticle]] = {}

    for article in articles:
        theme = _article_watch_theme(article) or "기타"
        by_theme.setdefault(theme, []).append(article)

    lines = ["📈 RESEARCH UPDATE 07:50", ""]

    for theme, grouped in by_theme.items():
        market_label = _market_label(grouped)
        lines.append(f"[{_theme_label(theme)} | {market_label}]")

        for article in grouped[:2]:
            lines.extend(_article_block(article, theme))
            lines.append("")

    return "\n".join(lines).strip()


def _article_block(article: NewsArticle, theme: str) -> list[str]:
    source = article.source or "Unknown"
    title = _short_title(article.title, limit=88)

    return [
        f"- {source}:",
        f"  {title}",
        "",
        f"  {_market_interpretation(article, theme)}",
        f"  {_watchpoint(article, theme)}",
    ]


def _market_interpretation(article: NewsArticle, theme: str) -> str:
    text = _article_text(article)
    label = _theme_label(theme)
    change = _matching_change_label(text)

    if any(token in text for token in OPINION_TOKENS):
        return "개별 의견 성격이 강한 코멘트로 시장 전체 영향은 제한적일 수 있습니다. 실제 실적과 수주 흐름 확인이 우선입니다."

    if theme == "기타":
        return "개별 종목 실적 발표 성격이 강해 시장 전체 영향은 제한적일 수 있습니다."

    if any(token in text for token in ("ai", "hbm", "data center", "semiconductor", "tsmc", "nvidia")):
        if any(token in text for token in NEGATIVE_TOKENS):
            return "AI반도체 밸류체인 기대가 일부 약해질 수 있어 HBM·장비주 변동성 확대 여부를 확인할 필요가 있습니다."
        return "TSMC·AI 서버 수요 기대가 이어지며 AI반도체·HBM 투자심리 유지 가능성이 있습니다. 반도체 장비와 전력설비 흐름도 함께 체크할 필요가 있습니다."

    if any(token in text for token in ("power", "grid", "transformer", "전력", "변압기", "전선")):
        return "전력망 투자 확대 기대가 유지되며 전선·변압기·전력설비 관련 종목 관심 유지 가능성이 있습니다."

    if any(token in text for token in ("copper", "구리", "infrastructure")):
        return "구리 가격과 전력인프라 투자 기대가 연결되며 전선·전력기기 섹터 매수세 유입 여부를 확인할 필요가 있습니다."

    if any(token in text for token in ("ess", "battery storage", "energy storage")):
        return "ESS 투자 확대 기대가 이어질 경우 전력인프라·배터리 장비주 강세 흐름 지속 여부가 중요합니다."

    if any(token in text for token in ("defense", "missile", "방산")):
        return "방산 수출 기대가 유지되며 실적 기반 수주 모멘텀 종목 중심으로 관심이 이어질 수 있습니다."

    if any(token in text for token in ("shipbuilding", "lng", "조선")):
        return "LNG선과 조선 발주 기대가 유지될 경우 조선·기자재 섹터 투자심리 개선 가능성이 있습니다."

    if any(token in text for token in ("robot", "automation", "로봇")):
        return "자동화 투자 확대 기대가 이어질 경우 로봇·FA 관련주 변동성 확대 가능성이 있습니다."

    if any(token in text for token in ("nuclear", "smr", "원전")):
        return "원전 정책과 전력 수요 확대 기대가 이어지며 SMR·원전 기자재 관련주 관심 유지 가능성이 있습니다."

    if change:
        return f"{label} 관련 {change} 내용으로 단기 투자심리에 영향을 줄 수 있어 장중 거래대금 반응 확인이 필요합니다."

    return f"{label} 관련 투자 포인트가 재확인된 자료로 관련 종목 강세 흐름 지속 여부를 체크할 필요가 있습니다."


def _watchpoint(article: NewsArticle, theme: str) -> str:
    text = _article_text(article)

    if "ai" in text or "hbm" in text or "semiconductor" in text:
        return "반도체 장비·HBM·전력설비 동반 강세 여부 체크 필요."

    if "power" in text or "grid" in text or "transformer" in text:
        return "전선·변압기·전력기기 대장주 거래대금 체크 필요."

    if "ess" in text:
        return "ESS·전력인프라 동반 움직임 여부 체크 필요."

    if "defense" in text or "방산" in text:
        return "수출 계약·실적 추정 변화 확인 필요."

    if "shipbuilding" in text or "lng" in text:
        return "LNG선·해양플랜트 발주 뉴스 체크 필요."

    if theme == "기타":
        return "개별 종목 중심 뉴스인지 섹터 확산 여부 확인 필요."

    return f"{_theme_label(theme)} 관련 대장주 거래대금과 후속 리포트 체크 필요."


def _market_label(articles: list[NewsArticle]) -> str:
    if any(article.market == "overseas" for article in articles):
        return "해외"
    return "국내"


def _theme_label(theme: str) -> str:
    if theme == "구리/전력인프라":
        return "전력인프라"
    return theme


def _article_text(article: NewsArticle) -> str:
    return f"{article.title} {article.summary}".lower()


def _matching_change_label(text: str) -> str | None:
    for label, keywords in CHANGE_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return label
    return None


def _article_watch_theme(article: NewsArticle) -> str | None:
    themes = _article_watch_themes(article)
    return themes[0] if themes else None


def _article_watch_themes(article: NewsArticle) -> list[str]:
    text = _article_text(article)
    themes = [theme for theme in article.themes if theme in WATCH_THEMES]

    for theme, keywords in THEME_FALLBACK_RULES:
        if theme in themes:
            continue

        if any(keyword.lower() in text for keyword in keywords):
            themes.append(theme)

    return themes


def _surge_themes(articles: list[NewsArticle]) -> set[str]:
    counts: Counter[str] = Counter()

    for article in articles:
        for theme in _article_watch_themes(article):
            counts[theme] += 1

    return {theme for theme, count in counts.items() if count >= THEME_SURGE_THRESHOLD}


def _short_title(title: str, limit: int = 56) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip()

    if len(cleaned) <= limit:
        return cleaned

    shortened = cleaned[:limit].rstrip()

    for separator in (" | ", " - ", ": ", ", "):
        index = shortened.rfind(separator)
        if index >= int(limit * 0.55):
            shortened = shortened[:index].rstrip()
            break
    else:
        index = shortened.rfind(" ")
        if index >= int(limit * 0.6):
            shortened = shortened[:index].rstrip()

    return f"{shortened}…"


def _dedupe(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    result: list[NewsArticle] = []

    for article in articles:
        key_source = article.url or article.source_url or article.title
        key = re.sub(r"\s+", " ", key_source).strip().lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(article)

    return result
