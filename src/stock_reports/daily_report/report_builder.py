from __future__ import annotations

from datetime import datetime

from stock_reports.daily_report.models import DailyReport, MarketDataPoint, NewsArticle, ThemeScore


class DailyReportBuilder:
    def build(self, report: DailyReport) -> str:
        lines: list[str] = []
        lines.append(f"📰 {report.title}")
        lines.append(report.generated_at.strftime("%Y-%m-%d %H:%M"))
        lines.append("")
        lines.extend(self._build_today_market(report.market_snapshot.points, report.market_snapshot.summary_lines))
        lines.append("")
        lines.extend(self._build_theme_strength(report.theme_scores))
        lines.append("")
        lines.extend(self._build_section("🇰🇷 국내 증시", report.domestic_articles))
        lines.append("")
        lines.extend(self._build_section("🇺🇸 해외 증시", report.overseas_articles))
        return "\n".join(lines)

    def build_article_link_list(self, report: DailyReport) -> str:
        lines: list[str] = ["🔗 기사 원문 링크", ""]
        lines.extend(self._build_link_section("[국내]", report.domestic_articles, start_number=1))
        lines.append("")
        lines.extend(
            self._build_link_section(
                "[해외]",
                report.overseas_articles,
                start_number=len(report.domestic_articles) + 1,
            )
        )
        return "\n".join(lines).strip()

    def _build_today_market(self, points: list[MarketDataPoint], summary_lines: list[str]) -> list[str]:
        grouped = {
            "지수": ["KOSPI", "KOSDAQ", "NASDAQ", "SOX"],
            "환율/금리": ["USD/KRW", "US10Y", "DXY"],
            "원자재": ["WTI", "Gold", "Copper"],
            "리스크": ["VIX", "Bitcoin"],
        }
        by_name = {point.name: point for point in points}

        lines = ["━━━━━━━━━━━━━━━━━━", "TODAY MARKET", "━━━━━━━━━━━━━━━━━━"]
        for label, names in grouped.items():
            values = [self._format_market_point(by_name.get(name), name) for name in names]
            lines.append(f"[{label}] " + " | ".join(values))

        lines.append("")
        lines.extend(f"• {line}" for line in summary_lines[:3])
        return lines

    def _build_theme_strength(self, theme_scores: list[ThemeScore]) -> list[str]:
        if not theme_scores:
            return ["[오늘 강세 예상 테마]", "주요 테마는 뉴스 수집 후 산출됩니다."]

        lines = ["[오늘 강세 예상 테마]"]
        for theme in theme_scores:
            bar = "█" * max(1, theme.score)
            lines.append(f"{theme.name:<12} {bar}")
        return lines

    def _build_section(self, title: str, articles: list[NewsArticle]) -> list[str]:
        lines = ["━━━━━━━━━━━━━━━━━━", title, "━━━━━━━━━━━━━━━━━━"]
        if not articles:
            lines.append("투자 영향도가 높은 뉴스가 아직 선별되지 않았습니다.")
            return lines

        for article in articles:
            lines.extend(self._build_article_card(article))
            lines.append("")
        return lines

    def _build_link_section(
        self,
        title: str,
        articles: list[NewsArticle],
        start_number: int,
    ) -> list[str]:
        lines = [title]
        if not articles:
            lines.append("선별된 기사가 없습니다.")
            return lines

        for offset, article in enumerate(articles):
            number = start_number + offset
            lines.append(f"{number}. {article.title}")
            lines.extend(_article_urls(article))
            lines.append("")

        if lines[-1] == "":
            lines.pop()
        return lines

    def _build_article_card(self, article: NewsArticle) -> list[str]:
        summary_lines = _compact_summary(article.summary, max_lines=5)
        themes = " / ".join(article.themes) if article.themes else "시장 일반"
        stars = "★" * article.impact_score + "☆" * (5 - article.impact_score)

        lines = [
            f"[{article.title}]",
            "",
        ]
        lines.extend(summary_lines)
        lines.extend(
            [
                "",
                f"[영향 테마] {themes}",
                f"[영향 강도] {stars} ({article.impact_score}/5)",
                "[원문 기사 링크]",
                article.url,
            ]
        )
        return lines

    def _format_market_point(self, point: MarketDataPoint | None, fallback_name: str) -> str:
        if point is None or point.value is None:
            return f"{fallback_name} -"

        change = ""
        if point.change_pct is not None:
            sign = "+" if point.change_pct >= 0 else ""
            change = f" ({sign}{point.change_pct:.2f}%)"

        return f"{point.name} {point.value:,.2f}{change}"


def _compact_summary(summary: str, max_lines: int) -> list[str]:
    if not summary:
        return ["• 세부 내용은 원문 기사 확인 필요."]

    if "\n" in summary:
        lines = [line.strip(" •") for line in summary.splitlines() if line.strip(" •")]
    else:
        sentences = summary.replace("...", ".").split(".")
        lines = [sentence.strip() for sentence in sentences if sentence.strip()]

    if not lines:
        lines = [summary.strip()]

    return [f"• {line}" for line in lines[:max_lines]]


def _article_urls(article: NewsArticle) -> list[str]:
    urls: list[str] = []
    for line in article.url.splitlines():
        url = line.strip()
        if url and url not in urls:
            urls.append(url)
    return urls or ["원문 링크 없음"]
