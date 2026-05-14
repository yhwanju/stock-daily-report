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

            ticker_obj = yf.Ticker(ticker.symbol)

            # 실시간/최신 시장 데이터 우선 사용
            fast_info = getattr(ticker_obj, "fast_info", {}) or {}

            latest_raw = (
                fast_info.get("lastPrice")
                or fast_info.get("regularMarketPrice")
            )

            previous_raw = (
                fast_info.get("previousClose")
                or fast_info.get("regularMarketPreviousClose")
            )

            # fast_info 실패 시 fallback
            if latest_raw is None or previous_raw is None:
                history = ticker_obj.history(
                    period="2d",
                    interval="1d"
                )

                closes = history["Close"].dropna()

                if closes.empty:
                    raise ValueError("No market data returned.")

                latest_raw = float(closes.iloc[-1])

                previous_raw = (
                    float(closes.iloc[-2])
                    if len(closes) > 1
                    else latest_raw
                )

            latest = float(latest_raw) * ticker.scale
            previous = float(previous_raw) * ticker.scale

            change_pct = (
                ((latest - previous) / previous * 100)
                if previous
                else None
            )

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
    if not any(point.change_pct is not None for point in points):
        return [
            "시장 데이터 수집 대기 상태입니다. 지수·환율·금리 확인 후 장초반 대응이 필요합니다.",
            "테마 판단은 뉴스 강도와 대장주 거래대금으로 선별해야 합니다.",
            "데이터가 들어오면 SOX, 원/달러, 미국채 10년물 조합을 먼저 확인합니다.",
        ]

    nasdaq = _change(by_name, "NASDAQ")
    sox = _change(by_name, "SOX")
    vix = _change(by_name, "VIX")
    us10y = _change(by_name, "US10Y")
    dxy = _change(by_name, "DXY")
    copper = _change(by_name, "Copper")
    wti = _change(by_name, "WTI")
    bitcoin = _change(by_name, "Bitcoin")
    usdkrw = _change(by_name, "USD/KRW")

    return [
        _market_temperature_line(nasdaq=nasdaq, sox=sox, vix=vix, us10y=us10y, usdkrw=usdkrw),
        _theme_hint_line(sox=sox, copper=copper, wti=wti, bitcoin=bitcoin, vix=vix),
        _macro_check_line(us10y=us10y, dxy=dxy, usdkrw=usdkrw),
    ]


def _market_temperature_line(
    *,
    nasdaq: float,
    sox: float,
    vix: float,
    us10y: float,
    usdkrw: float,
) -> str:
    risk_on = (nasdaq > 0) + (sox > 0) + (vix < 0)
    risk_pressure = (vix > 2) + (nasdaq < -0.7) + (us10y > 1) + (usdkrw > 0.5)

    if risk_pressure >= 2:
        return "변동성 경계 구간입니다. 지수 하락 폭, 환율, VIX 안정 여부를 먼저 확인해야 합니다."
    if risk_on >= 2 and sox > 0.5:
        return "위험선호가 살아 있고 반도체 지수가 앞서갑니다. 국내 AI반도체와 장비주는 장초반 거래대금 확인이 필요합니다."
    if risk_on >= 2:
        return "위험선호가 우위입니다. 성장주와 고베타주는 장초반 거래대금이 붙는지 봐야 합니다."
    return "방향성이 엇갈립니다. 지수보다 환율, 금리, 선물 흐름을 먼저 확인하는 장입니다."


def _theme_hint_line(*, sox: float, copper: float, wti: float, bitcoin: float, vix: float) -> str:
    if sox > 0.5 and copper > 0.5:
        return "SOX와 구리가 함께 강합니다. AI반도체, HBM, 전력설비를 같은 바구니로 점검해야 합니다."
    if sox > 0.5:
        return "SOX 강세가 뚜렷합니다. AI반도체·HBM·장비주가 장초반 주도권을 잡는지 확인해야 합니다."
    if copper > 0.5:
        return "구리 강세가 이어집니다. 전력인프라·전선·변압기 쪽 후속 뉴스가 중요합니다."
    if wti > 0.8:
        return "유가가 강합니다. 정유·화학보다 비용 부담 업종까지 함께 점검해야 합니다."
    if bitcoin > 1.5 and vix < 0:
        return "비트코인 반등과 VIX 하락이 겹쳤습니다. 성장주 반응 강도를 확인해야 합니다."
    return "테마는 뉴스 강도와 대장주 거래대금으로 선별해야 합니다."


def _macro_check_line(*, us10y: float, dxy: float, usdkrw: float) -> str:
    if us10y <= 0 and dxy <= 0 and usdkrw <= 0:
        return "금리와 달러가 안정적이면 성장주 반등이 이어질 여지가 있습니다."
    if us10y > 1 or dxy > 0.3 or usdkrw > 0.5:
        return "금리·환율 부담이 커진 구간입니다. 밸류에이션 민감 업종은 추격을 늦춰야 합니다."
    return "금리·환율은 방향성이 뚜렷하지 않습니다. 장중 변동성 확대 여부를 확인해야 합니다."


def _change(points: dict[str, MarketDataPoint], name: str) -> float:
    value = points.get(name)
    if value is None or value.change_pct is None:
        return 0.0
    return value.change_pct
