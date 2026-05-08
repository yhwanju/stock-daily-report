from __future__ import annotations

from datetime import datetime

from stock_reports.core.config import TickerConfig
from stock_reports.daily_report.models import MarketDataPoint, MarketSnapshot


class MarketDataCollector:
    def collect(self, tickers: list[TickerConfig]) -> MarketSnapshot:
        points = [self._fetch_ticker(item) for item in tickers]
        return MarketSnapshot(
            captured_at=datetime.now(),
            points=points,
            summary_lines=_summarize_market(points),
        )

    def _fetch_ticker(self, ticker: TickerConfig) -> MarketDataPoint:
        try:
            import yfinance as yf

            history = yf.Ticker(ticker.symbol).history(period="5d", interval="1d")
            closes = history["Close"].dropna()
            if closes.empty:
                raise ValueError("No close price returned.")

            latest = float(closes.iloc[-1]) * ticker.scale
            previous = float(closes.iloc[-2]) * ticker.scale if len(closes) > 1 else latest
            change_pct = ((latest - previous) / previous * 100) if previous else None

            return MarketDataPoint(
                name=ticker.name,
                category=ticker.category,
                value=latest,
                change_pct=change_pct,
                symbol=ticker.symbol,
            )
        except Exception:
            return MarketDataPoint(
                name=ticker.name,
                category=ticker.category,
                value=None,
                change_pct=None,
                symbol=ticker.symbol,
            )


def _summarize_market(points: list[MarketDataPoint]) -> list[str]:
    by_name = {point.name: point for point in points}

    nasdaq = _change(by_name, "NASDAQ")
    sox = _change(by_name, "SOX")
    vix = _change(by_name, "VIX")
    us10y = _change(by_name, "US10Y")
    copper = _change(by_name, "Copper")
    usdkrw = _change(by_name, "USD/KRW")

    risk_on = (nasdaq > 0) + (sox > 0) + (vix < 0)
    lines: list[str] = []

    if risk_on >= 2:
        lines.append("위험선호 우세. 성장주와 반도체 중심의 매수 심리 확인 필요.")
    elif vix > 2 or nasdaq < -0.7:
        lines.append("위험회피 우세. 변동성 확대 구간에서는 방어적 접근 필요.")
    else:
        lines.append("중립적 시장 흐름. 장 초반 수급과 환율 방향성이 중요.")

    if sox > 0.5:
        lines.append("AI반도체·HBM·전력설비 테마 강세 가능성.")
    elif copper > 0.5:
        lines.append("구리 강세로 전력인프라·산업재 관심 유지 가능.")
    else:
        lines.append("강세 테마는 뉴스 모멘텀과 외국인 수급 확인 필요.")

    if us10y <= 0 and usdkrw <= 0:
        lines.append("금리와 환율 안정 시 성장주 우호적 흐름 지속 가능.")
    elif us10y > 1 or usdkrw > 0.5:
        lines.append("금리·환율 부담이 커질 경우 밸류에이션 민감 업종은 주의.")
    else:
        lines.append("금리·환율은 뚜렷한 방향성보다 장중 변동성 점검 필요.")

    return lines[:3]


def _change(points: dict[str, MarketDataPoint], name: str) -> float:
    value = points.get(name)
    if value is None or value.change_pct is None:
        return 0.0
    return value.change_pct
