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
INSTITUTIONAL_TOKENS = ("goldman", "morgan stanley", "jp morgan", "reuters", "brokerage", "institutional")
NEGATIVE_TOKENS = ("downgrade", "target price cut", "price target cut", "cut its rating", "하향", "둔화", "slowdown")
POSITIVE_TOKENS = ("upgrade", "raised", "outlook", "상향", "개선")


def select_research_updates(articles: list[NewsArticle], max_items: int = 5) -> list[NewsArticle]:
    matches: list[NewsArticle] = []
    for article in articles:
        text = _article_text(article)
        if not _matching_change_label(text):
            continue
        if _article_watch_theme(article):
            matches.append(article)

    if len(matches) >= max_items:
        return _dedupe(matches)[:max_items]

    surge_themes = _surge_themes(articles)
    for article in articles:
        if article in matches:
            continue
        theme = _article_watch_theme(article)
        if theme is None or theme not in surge_themes:
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
        theme = _article_watch_theme(article) or "기타"
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
    text = _article_text(article)
    change = _matching_change_label(text)
    topic = _topic_phrase(text, theme)

    if any(token in text for token in OPINION_TOKENS):
        return f"개별 의견 중심 코멘트입니다. {topic}을 실제 실적 변수와 분리해 봐야 합니다."
    if any(token in text for token in INSTITUTIONAL_TOKENS):
        return f"기관 리포트가 {topic}을 근거로 {change or '전망 변화'}을 제시했습니다."
    if change:
        return f"{topic} 관련 {change} 내용입니다."
    if any(token in text for token in ("ai", "hbm", "data center", "semiconductor", "tsmc")):
        return "AI 투자와 데이터센터 증설 논리가 다시 확인된 자료입니다."
    if any(token in text for token in ("power", "grid", "infrastructure", "전력")):
        return "전력망 투자와 설비 증설 논리가 다시 확인된 자료입니다."
    if any(token in text for token in ("earnings", "guidance", "estimate", "실적")):
        return "실적 전망 변화가 핵심인 리포트입니다."
    return f"{topic}을 중심으로 투자 포인트가 정리된 자료입니다."


def _market_impact(article: NewsArticle, theme: str) -> str:
    text = _article_text(article)
    label = _theme_label(theme)

    if any(token in text for token in OPINION_TOKENS):
        return "단기 반응은 클 수 있지만, 반복 가능한 근거인지 원문 확인이 먼저입니다."
    if any(token in text for token in NEGATIVE_TOKENS):
        return f"{label} 쪽은 추격보다 하락 근거와 실적 민감도 확인이 먼저입니다."
    if any(token in text for token in POSITIVE_TOKENS):
        return f"{label} 쪽은 리포트 근거가 장중 거래대금으로 이어지는지 확인해야 합니다."
    if any(token in text for token in ("ai", "hbm", "data center", "semiconductor", "tsmc")):
        return "국내 HBM·장비·전력설비까지 기대가 번질 수 있어 대장주 반응을 같이 봐야 합니다."
    if any(token in text for token in ("power", "grid", "copper", "전력", "구리")):
        return "전력설비·전선·변압기 쪽 후속 뉴스와 장중 강도 비교가 필요합니다."
    return f"{label} 기사 수가 늘어난 구간이라 주도주와 거래대금을 함께 확인해야 합니다."


def _watchpoint(article: NewsArticle, theme: str) -> str:
    text = _article_text(article)
    if "ai" in text or "hbm" in text or "semiconductor" in text:
        return "체크: HBM·장비·전력설비가 함께 움직이는지"
    if "ess" in text or "battery storage" in text:
        return "체크: ESS와 전력인프라 대장주 거래대금"
    if "power" in text or "grid" in text or "infrastructure" in text or "copper" in text:
        return "체크: 전선·변압기·구리 가격 동조 여부"
    if "defense" in text or "missile" in text or "방산" in text:
        return "체크: 수출 계약과 실적 추정 변화"
    if "shipbuilding" in text or "lng" in text or "조선" in text:
        return "체크: LNG선·해양플랜트 발주 뉴스"
    return f"체크: {_theme_label(theme)} 대장주 거래대금과 후속 리포트"


def _source_hint(article: NewsArticle) -> str:
    return f" (참고: {article.source} | {_short_title(article.title)})"


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


def _topic_phrase(text: str, theme: str) -> str:
    if any(token in text for token in ("ai", "hbm", "data center", "semiconductor", "nvidia", "tsmc")):
        return "AI 서버 투자와 반도체 밸류체인"
    if any(token in text for token in ("power", "grid", "transformer", "전력", "전선", "변압기")):
        return "전력망 투자와 설비 증설"
    if any(token in text for token in ("copper", "구리")):
        return "구리 가격과 전력인프라"
    if any(token in text for token in ("ess", "battery storage", "energy storage")):
        return "전력 저장장치 투자"
    if any(token in text for token in ("defense", "missile", "방산")):
        return "방산 수출과 수주"
    if any(token in text for token in ("shipbuilding", "lng", "조선")):
        return "선박 발주와 조선 기자재"
    if any(token in text for token in ("robot", "automation", "로봇")):
        return "자동화 투자와 로봇"
    if any(token in text for token in ("nuclear", "smr", "원전")):
        return "원전 정책과 전력 수요"
    if any(token in text for token in ("earnings", "guidance", "estimate", "실적")):
        return "실적 전망"
    return f"{_theme_label(theme)} 밸류체인"


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
