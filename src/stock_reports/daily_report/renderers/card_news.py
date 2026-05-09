from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from stock_reports.daily_report.models import DailyReport, MarketDataPoint, NewsArticle, ThemeScore


CARD_WIDTH = 1080
CARD_HEIGHT = 1350
ARTICLES_PER_PAGE = 2

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

POSITIVE_KEYWORDS = (
    "강세",
    "개선",
    "확대",
    "매수세",
    "매수 심리",
    "외국인 순매수",
    "금리 하락",
    "달러 약세",
)

NEGATIVE_KEYWORDS = (
    "약세",
    "하락",
    "위험회피",
    "리스크",
    "변동성",
    "금리 상승",
    "달러 강세",
    "관망",
)

THEME_KEYWORDS = (
    "AI반도체",
    "AI 반도체",
    "HBM",
    "전력설비",
    "전력인프라",
    "원전",
    "ESS",
    "우주항공",
    "방산",
    "성장주",
    "반도체",
)

NEUTRAL_KEYWORDS = ("수급 확인", "선별 대응", "중립", "혼조")

MARKET_HIGHLIGHT_STYLES = {
    "market-hl-positive": "color:#0f9f6e;font-weight:1000;",
    "market-hl-negative": "color:#d84a4a;font-weight:1000;",
    "market-hl-theme": "color:#0755d8;font-weight:1000;",
    "market-hl-neutral": "color:#5f6b7a;font-weight:1000;",
}


@dataclass(frozen=True)
class CardPage:
    slide_class: str
    content: str


class CardNewsRenderer:
    def __init__(self, template_dir: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.template_dir = template_dir or base_dir / "templates"
        self.template = (self.template_dir / "card_news.html").read_text(encoding="utf-8")
        self.css = (self.template_dir / "card_news.css").read_text(encoding="utf-8")

    def render_pngs(self, report: DailyReport, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = self._build_pages(report)
        date_token = report.generated_at.strftime("%Y%m%d")
        output_paths = [
            output_dir / f"daily_report_{date_token}_card_{index:02d}.png"
            for index in range(1, len(pages) + 1)
        ]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "card_news PNG 생성을 위해 playwright가 필요합니다. "
                "`pip install -r requirements.txt` 후 `python -m playwright install chromium`을 실행하세요."
            ) from exc

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except Exception as exc:
                raise RuntimeError(
                    "Chromium 실행에 실패했습니다. "
                    "`python -m playwright install chromium`을 먼저 실행하세요."
                ) from exc
            try:
                page = browser.new_page(
                    viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
                    device_scale_factor=1,
                )
                for card_page, output_path in zip(pages, output_paths):
                    page.set_content(self._html_for_page(report, card_page), wait_until="networkidle")
                    page.locator(".slide").screenshot(path=str(output_path))
            finally:
                browser.close()

        return output_paths

    def _html_for_page(self, report: DailyReport, page: CardPage) -> str:
        return (
            self.template.replace("{{ title }}", escape(report.title))
            .replace("{{ css }}", self.css)
            .replace("{{ slide_class }}", page.slide_class)
            .replace("{{ content }}", page.content)
        )

    def _build_pages(self, report: DailyReport) -> list[CardPage]:
        domestic_articles = _valid_link_articles(report.domestic_articles)
        overseas_articles = _valid_link_articles(report.overseas_articles)

        pages = [
            CardPage("cover", self._cover_page(report)),
            CardPage("today-market", self._market_page(report)),
            CardPage("themes", self._theme_page(report.theme_scores)),
        ]

        pages.extend(
            self._news_pages(
                title="국내 증시 뉴스",
                subtitle="장 시작 전 확인할 국내 핵심 재료",
                articles=domestic_articles,
                start_page_number=len(pages) + 1,
                number_offset=0,
            )
        )
        pages.extend(
            self._news_pages(
                title="해외 증시 뉴스",
                subtitle="미국장과 글로벌 자금 흐름 체크",
                articles=overseas_articles,
                start_page_number=len(pages) + 1,
                number_offset=len(domestic_articles),
            )
        )
        return pages

    def _cover_page(self, report: DailyReport) -> str:
        insight = _cover_insight_html(report)
        date_text = report.generated_at.strftime("%Y.%m.%d")
        return f"""
        <section class="frame">
          <div>
            <span class="eyebrow">DAILY MARKET BRIEF</span>
            <h1 class="cover-title">오늘의<br />시장 브리프</h1>
            <div class="cover-date">{escape(date_text)}</div>
            <div class="hero-card">
              <span class="hero-label">오늘 시장 한줄 판단</span>
              <div class="hero-text">{insight}</div>
            </div>
          </div>
          <div class="footer">
            <span>Stock Daily Report</span>
            <span>Before Market Open</span>
          </div>
        </section>
        """

    def _market_page(self, report: DailyReport) -> str:
        by_name = {point.name: point for point in report.market_snapshot.points}
        indices = ["KOSPI", "KOSDAQ", "NASDAQ", "SOX"]
        macro = ["USD/KRW", "US10Y", "DXY", "WTI", "Gold", "Copper", "VIX", "Bitcoin"]

        return f"""
        <section class="frame">
          {_page_header("02", "TODAY MARKET", "지수와 매크로를 한 장으로 압축")}
          <div class="market-grid">
            <div class="section-card">
              <span class="section-title">지수</span>
              <div class="metric-list">
                {''.join(_metric_row(by_name.get(name), name) for name in indices)}
              </div>
            </div>
            <div class="section-card">
              <span class="section-title">매크로 / 원자재 / 리스크</span>
              <div class="metric-list">
                {''.join(_metric_row(by_name.get(name), name) for name in macro)}
              </div>
            </div>
          </div>
        </section>
        """

    def _theme_page(self, theme_scores: list[ThemeScore]) -> str:
        top_themes = theme_scores[:5]
        if not top_themes:
            body = '<div class="empty">오늘 강세 예상 테마는 뉴스 수집 후 산출됩니다.</div>'
        else:
            body = f"""
            <div class="theme-list">
              {''.join(_theme_card(theme) for theme in top_themes)}
            </div>
            """

        return f"""
        <section class="frame">
          {_page_header("03", "오늘 강세 예상 테마", "뉴스 영향도 기준 TOP5")}
          {body}
        </section>
        """

    def _news_pages(
        self,
        title: str,
        subtitle: str,
        articles: list[NewsArticle],
        start_page_number: int,
        number_offset: int,
    ) -> list[CardPage]:
        chunks = _chunks(articles, ARTICLES_PER_PAGE) or [[]]
        pages: list[CardPage] = []
        for offset, chunk in enumerate(chunks):
            page_number = start_page_number + offset
            if chunk:
                cards = "".join(
                    _news_card(
                        article,
                        number=number_offset + offset * ARTICLES_PER_PAGE + index,
                    )
                    for index, article in enumerate(chunk, start=1)
                )
                body = f'<div class="news-grid">{cards}</div>'
            else:
                body = '<div class="empty">투자 영향도가 높은 뉴스가 아직 선별되지 않았습니다.</div>'

            pages.append(
                CardPage(
                    "news-page",
                    f"""
                    <section class="frame">
                      {_page_header(f"{page_number:02d}", title, subtitle)}
                      {body}
                    </section>
                    """,
                )
            )

        return pages


def build_discord_card_summary(report: DailyReport, image_paths: list[Path]) -> str:
    insight = _cover_insight_text(report)
    themes = ", ".join(theme.name for theme in report.theme_scores[:5]) or "주요 테마 산출 대기"
    total_articles = len(_valid_link_articles(report.domestic_articles)) + len(_valid_link_articles(report.overseas_articles))
    lines = [
        f"📰 {report.title}",
        report.generated_at.strftime("%Y-%m-%d %H:%M"),
        "",
        f"오늘 판단: {insight}",
        f"강세 예상 테마: {themes}",
        f"선별 기사: {total_articles}개",
        f"카드뉴스: {len(image_paths)}장 첨부",
    ]
    return "\n".join(lines)


def _page_header(number: str, title: str, subtitle: str) -> str:
    return f"""
    <header class="page-header">
      <div>
        <h2 class="page-title">{escape(title)}</h2>
        <p class="page-subtitle">{escape(subtitle)}</p>
      </div>
      <span class="page-kicker">{escape(number)}</span>
    </header>
    """


def _metric_row(point: MarketDataPoint | None, fallback_name: str) -> str:
    if point is None or point.value is None:
        return f"""
        <div class="metric-row">
          <span class="metric-name">{escape(fallback_name)}</span>
          <span class="metric-value flat">-</span>
        </div>
        """

    change = point.change_pct
    if change is None:
        change_class = "flat"
        change_text = "-"
    else:
        change_class = "up" if change >= 0 else "down"
        sign = "+" if change >= 0 else ""
        change_text = f"{sign}{change:.2f}%"

    return f"""
    <div class="metric-row">
      <span class="metric-name">{escape(point.name)}</span>
      <span class="metric-value {change_class}">
        {point.value:,.2f}
        <span class="metric-change {change_class}">{escape(change_text)}</span>
      </span>
    </div>
    """


def _theme_card(theme: ThemeScore) -> str:
    stars = _stars(_theme_star_score(theme.score))
    width = min(100, max(12, theme.score * 10))
    return f"""
    <article class="theme-card">
      <div class="theme-top">
        <span class="theme-name">{escape(theme.name)}</span>
        <span class="stars">{stars}</span>
      </div>
      <div class="bar"><div class="bar-fill" style="width: {width}%"></div></div>
    </article>
    """


def _news_card(article: NewsArticle, number: int) -> str:
    summary_lines = _summary_lines(article.summary)[:5]
    tags = article.themes[:4] or ["시장 일반"]
    return f"""
    <article class="news-card">
      <div class="news-head">
        <span class="num-badge">{number:02d}</span>
        <h3 class="headline">{escape(article.title)}</h3>
      </div>
      <div class="summary">
        {''.join(f'<p>{escape(line)}</p>' for line in summary_lines)}
      </div>
      <div class="meta">
        <div class="tags">
          {''.join(f'<span class="tag">{escape(tag)}</span>' for tag in tags)}
        </div>
        <span class="impact-badge">{_stars(article.impact_score)} {article.impact_score}/5</span>
      </div>
    </article>
    """


def _cover_insight(report: DailyReport) -> str:
    return _cover_insight_text(report)


def _cover_insight_text(report: DailyReport) -> str:
    return " ".join(_cover_insight_lines(report))


def _cover_insight_html(report: DailyReport) -> str:
    return "".join(
        f'<span class="hero-line">{_highlight_market_text(line)}</span>'
        for line in _cover_insight_lines(report)
    )


def _cover_insight_lines(report: DailyReport) -> list[str]:
    lines = _cover_summary_from_market_points(report.market_snapshot.points)
    return lines[:2] or ["장 초반 지수·환율·수급 확인이 우선입니다."]


def _cover_summary_from_market_points(points: list[MarketDataPoint]) -> list[str]:
    changes = {point.name: point.change_pct for point in points if point.change_pct is not None}
    if not changes:
        return [
            "시장 데이터 수집 대기 상태라 장 초반 지수·환율·수급 확인이 우선입니다.",
            "뉴스 모멘텀과 거래대금이 붙는 업종을 먼저 선별해야 합니다.",
        ]

    cause = _cover_market_cause(changes)
    themes = _cover_market_themes(changes)

    if _cover_is_risk_off(changes):
        return [
            f"{cause}로 위험회피 심리가 커지고 있습니다.",
            f"{themes} 중심의 선별 대응이 필요합니다.",
        ]

    flow, verb = _cover_money_flow(changes)
    theme_reason = _cover_theme_reason(changes)
    return [
        f"{cause}로 {flow}가 {verb}.",
        f"{theme_reason} {themes} 강세 가능성이 높습니다.",
    ]


def _cover_market_cause(changes: dict[str, float]) -> str:
    causes: list[str] = []
    us10y = _change(changes, "US10Y")
    dxy = _change(changes, "DXY")
    usdkrw = _change(changes, "USD/KRW")
    sox = _change(changes, "SOX")
    copper = _change(changes, "Copper")
    wti = _change(changes, "WTI")
    vix = _change(changes, "VIX")

    if us10y <= -0.15:
        causes.append("미국채 금리 하락")
    elif us10y <= 0.1:
        causes.append("미국채 금리 안정")
    elif us10y >= 1:
        causes.append("미국채 금리 상승")

    if dxy < 0 or usdkrw <= -0.2:
        causes.append("달러 약세")
    elif dxy >= 0.3 or usdkrw >= 0.5:
        causes.append("달러 강세")

    if sox >= 0.5:
        causes.append("AI 수요 기대")
    if copper >= 0.5:
        causes.append("구리 가격 강세")
    if wti >= 0.8:
        causes.append("유가 상승")
    if vix >= 2:
        causes.append("변동성 확대")

    if not causes:
        return "금리·환율 방향성 혼재"
    return _join_phrases(causes[:2])


def _cover_money_flow(changes: dict[str, float]) -> tuple[str, str]:
    sox = _change(changes, "SOX")
    nasdaq = _change(changes, "NASDAQ")
    us10y = _change(changes, "US10Y")
    usdkrw = _change(changes, "USD/KRW")
    kospi = _change(changes, "KOSPI")
    kosdaq = _change(changes, "KOSDAQ")
    vix = _change(changes, "VIX")

    if sox >= 0.5 and us10y <= 0.1:
        return "성장주·반도체 매수 심리", "개선되고 있습니다"
    if sox >= 0.5:
        return "반도체 중심 매수세", "확대되고 있습니다"
    if nasdaq >= 0.5 and us10y <= 0.1:
        return "성장주 매수 심리", "개선되고 있습니다"
    if usdkrw <= -0.2 and (kospi > 0 or kosdaq > 0):
        return "외국인 순매수 기대", "커지고 있습니다"
    if vix < 0:
        return "성장주 매수 심리", "개선되고 있습니다"
    return "장 초반 수급 확인 심리", "이어지고 있습니다"


def _cover_theme_reason(changes: dict[str, float]) -> str:
    if _change(changes, "SOX") >= 0.5:
        return "AI 수요 기대가 이어지며"
    if _change(changes, "Copper") >= 0.5:
        return "구리 가격 강세가 이어지며"
    if _change(changes, "WTI") >= 0.8:
        return "유가 상승 영향으로"
    return "뉴스 모멘텀이 이어지며"


def _cover_market_themes(changes: dict[str, float]) -> str:
    themes: list[str] = []
    if _change(changes, "SOX") >= 0.5:
        themes.extend(["AI반도체", "HBM", "전력인프라"])
    elif _change(changes, "NASDAQ") >= 0.5 and _change(changes, "US10Y") <= 0.1:
        themes.extend(["AI반도체", "성장주"])

    if _change(changes, "Copper") >= 0.5:
        themes.append("전력설비")
    if _change(changes, "WTI") >= 0.8:
        themes.append("에너지")
    if _cover_is_risk_off(changes) and not themes:
        themes.extend(["방산", "배당주"])
    if not themes:
        themes.extend(["AI반도체", "전력설비", "실적주"])

    return "·".join(dict.fromkeys(themes[:3]))


def _cover_is_risk_off(changes: dict[str, float]) -> bool:
    return (
        _change(changes, "VIX") >= 2
        or _change(changes, "NASDAQ") <= -0.7
        or _change(changes, "US10Y") >= 1
        or _change(changes, "USD/KRW") >= 0.5
    )


def _highlight_market_text(text: str) -> str:
    keyword_classes = {
        **{keyword: "market-hl-positive" for keyword in POSITIVE_KEYWORDS},
        **{keyword: "market-hl-negative" for keyword in NEGATIVE_KEYWORDS},
        **{keyword: "market-hl-theme" for keyword in THEME_KEYWORDS},
        **{keyword: "market-hl-neutral" for keyword in NEUTRAL_KEYWORDS},
    }
    keywords = sorted(keyword_classes, key=len, reverse=True)

    highlighted: list[str] = []
    index = 0
    while index < len(text):
        matched = next((keyword for keyword in keywords if text.startswith(keyword, index)), None)
        if matched:
            css_class = keyword_classes[matched]
            style = MARKET_HIGHLIGHT_STYLES[css_class]
            highlighted.append(
                f'<strong class="market-hl {css_class}" style="{style}">{escape(matched)}</strong>'
            )
            index += len(matched)
            continue

        highlighted.append(escape(text[index]))
        index += 1

    return "".join(highlighted)


def _join_phrases(values: list[str]) -> str:
    if len(values) <= 1:
        return values[0] if values else "매크로 방향성 혼재"
    first, second = values[0], values[1]
    particle = "과" if _has_final_consonant(first) else "와"
    return f"{first}{particle} {second}"


def _has_final_consonant(text: str) -> bool:
    for character in reversed(text.strip()):
        code = ord(character)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
    return True


def _change(points: dict[str, float], name: str) -> float:
    return points.get(name, 0.0)


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _negative(value: float | None) -> bool:
    return value is not None and value < 0


def _above(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def _below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def _summary_lines(summary: str) -> list[str]:
    lines = [line.strip(" •") for line in summary.splitlines() if line.strip(" •")]
    if lines:
        return lines
    return [summary.strip()] if summary.strip() else ["원문 기사 확인 필요"]


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


def _theme_star_score(score: int) -> int:
    return max(1, min(5, math.ceil(score / 2)))


def _stars(score: int) -> str:
    score = max(1, min(score, 5))
    return "★" * score + "☆" * (5 - score)


def _chunks(values: list[NewsArticle], size: int) -> list[list[NewsArticle]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
