from __future__ import annotations

from collections import Counter

from stock_reports.daily_report.models import NewsArticle, ThemeScore


THEME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("금리/FOMC", ("fomc", "fed", "연준", "금리", "treasury", "미국채", "rate cut", "rate hike")),
    ("CPI/물가", ("cpi", "물가", "inflation", "인플레이션", "pce", "소비자물가")),
    ("환율/달러", ("환율", "달러", "dollar", "dxy", "원화", "usd/krw", "yen", "엔화")),
    ("외국인 수급", ("외국인", "수급", "기관", "매수", "순매수", "foreign buying", "inflow")),
    ("AI반도체", ("nvidia", "엔비디아", "ai", "artificial intelligence", "인공지능", "반도체", "semiconductor", "chip")),
    ("HBM", ("hbm", "고대역폭", "high bandwidth memory", "dram", "d램")),
    ("전력설비", ("전력", "전력설비", "grid", "power infrastructure", "변압기", "전선", "송배전")),
    ("원전", ("원전", "nuclear", "smr", "reactor")),
    ("ESS", ("ess", "battery storage", "energy storage", "에너지저장")),
    ("우주항공", ("우주항공", "우주", "항공", "space", "aerospace", "satellite", "위성")),
    ("방산", ("방산", "defense", "defence", "missile", "미사일", "무기", "수출")),
    ("유가", ("유가", "oil", "wti", "crude", "opec")),
    ("구리/전력인프라", ("구리", "copper")),
    ("조선", ("조선", "shipbuilding", "lng선", "선박")),
    ("2차전지", ("2차전지", "battery", "배터리", "lithium", "리튬", "cathode", "양극재")),
    ("자동차", ("자동차", "ev", "전기차", "vehicle", "tesla", "테슬라", "hyundai", "현대차")),
    ("바이오", ("바이오", "bio", "pharma", "제약", "임상", "fda")),
    ("로봇", ("로봇", "robot", "robotics", "automation", "자동화")),
    ("정부 정책", ("정부", "정책", "규제", "지원책", "subsidy", "tariff", "관세")),
    ("대형 수주", ("수주", "contract", "order", "deal", "공급계약")),
    ("실적", ("실적", "earnings", "surprise", "guidance", "가이던스", "매출", "영업이익")),
    ("가상자산/위험선호", ("bitcoin", "비트코인", "crypto", "가상자산", "risk-on", "vix")),
)


class ThemeClassifier:
    def classify(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        for article in articles:
            article.themes = self.classify_one(article)
        return articles

    def classify_one(self, article: NewsArticle) -> list[str]:
        text = f"{article.title} {article.summary}".lower()
        themes = [
            theme
            for theme, keywords in THEME_RULES
            if any(keyword.lower() in text for keyword in keywords)
        ]
        return _unique(themes)

    def rank_themes(self, articles: list[NewsArticle]) -> list[ThemeScore]:
        counter: Counter[str] = Counter()
        for article in articles:
            for theme in article.themes:
                counter[theme] += max(1, article.impact_score)

        return [
            ThemeScore(name=name, score=min(score, 10))
            for name, score in counter.most_common(6)
        ]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
