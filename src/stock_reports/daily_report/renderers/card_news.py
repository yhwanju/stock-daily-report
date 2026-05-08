from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from pathlib import Path

from stock_reports.daily_report.models import DailyReport, MarketDataPoint, NewsArticle, ThemeScore


CARD_WIDTH = 1080
CARD_HEIGHT = 1350
ARTICLES_PER_PAGE = 2


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
        pages = [
            CardPage("cover", self._cover_page(report)),
            CardPage("today-market", self._market_page(report)),
            CardPage("themes", self._theme_page(report.theme_scores)),
        ]

        pages.extend(
            self._news_pages(
                title="국내 증시 뉴스",
                subtitle="장 시작 전 확인할 국내 핵심 재료",
                articles=report.domestic_articles,
                start_page_number=len(pages) + 1,
                number_offset=0,
            )
        )
        pages.extend(
            self._news_pages(
                title="해외 증시 뉴스",
                subtitle="미국장과 글로벌 자금 흐름 체크",
                articles=report.overseas_articles,
                start_page_number=len(pages) + 1,
                number_offset=len(report.domestic_articles),
            )
        )
        return pages

    def _cover_page(self, report: DailyReport) -> str:
        insight = _cover_insight(report)
        date_text = report.generated_at.strftime("%Y.%m.%d")
        return f"""
        <section class="frame">
          <div>
            <span class="eyebrow">DAILY MARKET BRIEF</span>
            <h1 class="cover-title">오늘의<br />시장 브리프</h1>
            <div class="cover-date">{escape(date_text)}</div>
            <div class="hero-card">
              <span class="hero-label">오늘 시장 한줄 판단</span>
              <p class="hero-text">{escape(insight)}</p>
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
    insight = _cover_insight(report)
    themes = ", ".join(theme.name for theme in report.theme_scores[:5]) or "주요 테마 산출 대기"
    total_articles = len(report.domestic_articles) + len(report.overseas_articles)
    return "\n".join(
        [
            f"📰 {report.title}",
            report.generated_at.strftime("%Y-%m-%d %H:%M"),
            "",
            f"오늘 판단: {insight}",
            f"강세 예상 테마: {themes}",
            f"선별 기사: {total_articles}개",
            f"카드뉴스: {len(image_paths)}장 첨부",
        ]
    )


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
          <span class="metric-value">-</span>
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
      <span class="metric-value">
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
    lines = report.market_snapshot.summary_lines
    if len(lines) >= 2:
        first = lines[0].split(".")[0].strip()
        second = lines[1].split(".")[0].strip()
        return f"{first}, {second}"
    if lines:
        return lines[0]
    return "장 초반 수급과 핵심 테마 확인 필요"


def _summary_lines(summary: str) -> list[str]:
    lines = [line.strip(" •") for line in summary.splitlines() if line.strip(" •")]
    if lines:
        return lines
    return [summary.strip()] if summary.strip() else ["원문 기사 확인 필요"]


def _theme_star_score(score: int) -> int:
    return max(1, min(5, math.ceil(score / 2)))


def _stars(score: int) -> str:
    score = max(1, min(score, 5))
    return "★" * score + "☆" * (5 - score)


def _chunks(values: list[NewsArticle], size: int) -> list[list[NewsArticle]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
