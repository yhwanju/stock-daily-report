from __future__ import annotations

from pathlib import Path

from stock_reports.daily_report.models import DailyReport, MarketDataPoint, NewsArticle, ThemeScore


WATCH_METRICS = ("NASDAQ", "SOX", "USD/KRW", "US10Y", "DXY", "VIX", "Bitcoin")


def build_discord_card_summary(report: DailyReport, image_paths: list[Path]) -> str:
    lines: list[str] = [
        "📰 DAILY MARKET BRIEF 07:45",
        report.generated_at.strftime("%Y-%m-%d %H:%M KST"),
        "",
        "📌 오늘 핵심",
    ]

    lines.extend(_bullet_lines(_market_summary_lines(report), max_items=2))
    lines.append("")
    lines.append("🔥 강세 예상 테마")
    lines.extend(_bullet_lines(_theme_lines(report.theme_scores), max_items=5))
    lines.append("")
    lines.append("⚠️ 체크 포인트")
    lines.extend(_bullet_lines(_metric_watch_lines(report.market_snapshot.points), max_items=4))
    lines.append("")
    lines.append("🗞 선별 뉴스")
    lines.extend(_bullet_lines(_news_lines(report), max_items=4))
    lines.append("")
    lines.append(f"📎 카드뉴스 {len(image_paths)}장 첨부")

    return "\n".join(lines).strip()


def _market_summary_lines(report: DailyReport) -> list[str]:
    if report.market_snapshot.summary_lines:
        return report.market_snapshot.summary_lines[:2]
    return ["장 초반 지수·환율·금리 방향성 확인이 우선입니다."]


def _theme_lines(themes: list[ThemeScore]) -> list[str]:
    if not themes:
        return ["주요 테마 산출 대기"]

    result: list[str] = []
    for theme in themes[:5]:
        result.append(f"{theme.name} {_stars(_theme_star_score(theme.score))} ({theme.score}/10)")
    return result


def _metric_watch_lines(points: list[MarketDataPoint]) -> list[str]:
    by_name = {point.name: point for point in points}
    result: list[str] = []

    for name in WATCH_METRICS:
        point = by_name.get(name)
        if point is None or point.change_pct is None or point.value is None:
            continue
        result.append(f"{name}: {point.value:,.2f} / {_format_change(point.change_pct)} — {_metric_comment(name, point.change_pct)}")

    return result or ["핵심 지표 데이터 확인 필요"]


def _news_lines(report: DailyReport) -> list[str]:
    domestic = _top_titles(report.domestic_articles, market_label="국내")
    overseas = _top_titles(report.overseas_articles, market_label="해외")
    return domestic + overseas or ["선별 뉴스 없음"]


def _top_titles(articles: list[NewsArticle], market_label: str) -> list[str]:
    result: list[str] = []
    for article in articles[:2]:
        title = _shorten(article.title, limit=70)
        themes = ", ".join(article.themes[:2]) if article.themes else "시장 일반"
        result.append(f"[{market_label}] {title} / {themes}")
    return result


def _metric_comment(name: str, change: float) -> str:
    if name == "NASDAQ":
        return "성장주 투자심리 개선" if change >= 0 else "성장주 부담 확대"
    if name == "SOX":
        return "AI반도체·HBM 관심 유지" if change >= 0 else "반도체 변동성 체크"
    if name == "USD/KRW":
        return "원화 약세, 외국인 매수 부담" if change >= 0 else "원화 강세, 외국인 매수 기대"
    if name == "US10Y":
        return "금리 상승, 성장주 부담" if change >= 0 else "금리 하락, 성장주 우호적"
    if name == "DXY":
        return "달러 강세, 위험자산 부담" if change >= 0 else "달러 약세, 투자심리 개선"
    if name == "VIX":
        return "변동성 확대 가능성" if change >= 0 else "위험회피 완화 신호"
    if name == "Bitcoin":
        return "위험자산 선호 확인" if change >= 0 else "투기심리 둔화 체크"
    return "장중 방향성 확인 필요"


def _bullet_lines(values: list[str], max_items: int) -> list[str]:
    return [f"- {value}" for value in values[:max_items]]


def _format_change(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _theme_star_score(score: int) -> int:
    return max(1, min(5, (score + 1) // 2))


def _stars(score: int) -> str:
    score = max(1, min(score, 5))
    return "★" * score + "☆" * (5 - score)


def _shorten(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}…"
