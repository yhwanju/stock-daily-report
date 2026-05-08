from __future__ import annotations

from datetime import datetime

from stock_reports.daily_report.models import MarketDataPoint, MarketSnapshot, NewsArticle


def sample_market_snapshot() -> MarketSnapshot:
    points = [
        MarketDataPoint("KOSPI", "indices", 2734.18, 0.42, "^KS11"),
        MarketDataPoint("KOSDAQ", "indices", 857.31, 0.68, "^KQ11"),
        MarketDataPoint("NASDAQ", "indices", 16511.18, 1.24, "^IXIC"),
        MarketDataPoint("SOX", "indices", 5128.74, 2.18, "^SOX"),
        MarketDataPoint("USD/KRW", "rates", 1362.40, -0.31, "KRW=X"),
        MarketDataPoint("US10Y", "rates", 4.42, -0.06, "^TNX"),
        MarketDataPoint("DXY", "rates", 104.15, -0.22, "DX-Y.NYB"),
        MarketDataPoint("WTI", "commodities", 78.34, 0.74, "CL=F"),
        MarketDataPoint("Gold", "commodities", 2348.20, 0.28, "GC=F"),
        MarketDataPoint("Copper", "commodities", 4.62, 1.15, "HG=F"),
        MarketDataPoint("VIX", "risks", 13.82, -4.18, "^VIX"),
        MarketDataPoint("Bitcoin", "risks", 68240.00, 1.96, "BTC-USD"),
    ]
    return MarketSnapshot(
        captured_at=datetime.now(),
        points=points,
        summary_lines=[
            "위험선호 우세. 성장주와 반도체 중심의 매수 심리 확인 필요.",
            "AI반도체·HBM·전력설비 테마 강세 가능성.",
            "금리와 환율 안정 시 성장주 우호적 흐름 지속 가능.",
        ],
    )


def sample_news_articles() -> list[NewsArticle]:
    now = datetime.now()
    return [
        NewsArticle(
            title="[샘플] 외국인 순매수 확대, 코스피 대형 반도체 중심 강세",
            summary="외국인 매수세가 반도체와 자동차 대형주로 집중되며 지수 상승을 이끌었다. 원화 안정과 미국 기술주 강세가 국내 위험선호를 자극했다.",
            url="https://example.com/domestic-foreign-buying",
            source="sample",
            market="domestic",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] HBM 공급 부족 전망에 국내 AI반도체 밸류체인 재부각",
            summary="AI 서버 투자 확대와 고대역폭메모리 수요 증가 전망이 함께 부각됐다. 장비·소재·패키징 업체로 관심이 확산되는 흐름이다.",
            url="https://example.com/domestic-hbm-supply",
            source="sample",
            market="domestic",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] 정부 전력망 투자 확대 검토, 전력설비·전선주 관심",
            summary="데이터센터와 산업 전력 수요 증가에 대응하기 위한 송배전 투자 확대 필요성이 제기됐다. 변압기와 전선 업종이 수혜 후보로 거론된다.",
            url="https://example.com/domestic-grid-policy",
            source="sample",
            market="domestic",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] 미국채 10년물 금리 하락, 성장주 밸류에이션 부담 완화",
            summary="미국채 금리가 물가 둔화 기대와 함께 하락했다. 금리 민감도가 높은 기술주와 성장주에 우호적인 환경이 형성됐다.",
            url="https://example.com/us10y-growth-stocks",
            source="sample",
            market="overseas",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] 엔비디아 상승, AI 서버 수요 기대가 반도체 지수 견인",
            summary="엔비디아와 주요 반도체주가 AI 서버 투자 기대를 반영하며 상승했다. SOX 지수 강세가 국내 반도체 투자심리에도 영향을 줄 수 있다.",
            url="https://example.com/nvidia-ai-server",
            source="sample",
            market="overseas",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] 구리 가격 상승, 전력 인프라와 산업재 수요 기대 반영",
            summary="구리 가격이 전력망 투자와 데이터센터 증설 기대를 반영하며 강세를 보였다. 전력설비와 산업재 관련 테마가 함께 주목된다.",
            url="https://example.com/copper-grid-demand",
            source="sample",
            market="overseas",
            published_at=now,
        ),
        NewsArticle(
            title="[샘플] 비트코인 반등과 VIX 하락, 위험자산 선호 회복 신호",
            summary="비트코인이 반등하고 VIX가 낮은 수준을 유지하며 위험자산 선호가 개선됐다. 단기적으로 성장주와 고베타 업종에 우호적일 수 있다.",
            url="https://example.com/risk-on-bitcoin-vix",
            source="sample",
            market="overseas",
            published_at=now,
        ),
    ]
