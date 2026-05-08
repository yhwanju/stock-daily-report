from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from stock_reports.core.config import NewsSourceConfig
from stock_reports.daily_report.models import NewsArticle


DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
}

MARKET_KEYWORDS = (
    "stock",
    "stocks",
    "market",
    "markets",
    "finance",
    "business",
    "economy",
    "fed",
    "fomc",
    "cpi",
    "yield",
    "nasdaq",
    "dow",
    "s&p",
    "nvidia",
    "semiconductor",
    "ai",
    "oil",
    "gold",
    "copper",
    "bitcoin",
    "증시",
    "주식",
    "증권",
    "코스피",
    "코스닥",
    "환율",
    "금리",
    "반도체",
    "외국인",
    "수급",
    "유가",
    "구리",
)


class NewsSourceClient(ABC):
    def __init__(self, source: NewsSourceConfig, max_items: int) -> None:
        self.source = source
        self.max_items = max_items

    @abstractmethod
    def fetch(self) -> list[NewsArticle]:
        raise NotImplementedError

    def _request(self) -> str:
        response = requests.get(
            self.source.url,
            headers=DEFAULT_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response.text

    def _article(
        self,
        title: str,
        url: str,
        summary: str = "",
        published_at: datetime | None = None,
    ) -> NewsArticle | None:
        title = clean_text(title)
        url = urljoin(self.source.url, clean_text(url))
        summary = clean_text(summary)

        if not title or not url.startswith("http"):
            return None

        return NewsArticle(
            title=title,
            summary=summary,
            url=url,
            source=self.source.name,
            market=self.source.market,
            published_at=published_at,
        )


class RSSNewsSource(NewsSourceClient):
    def fetch(self) -> list[NewsArticle]:
        soup = BeautifulSoup(self._request(), "html.parser")
        articles: list[NewsArticle] = []

        for item in soup.find_all("item")[: self.max_items]:
            article = self._article(
                title=_tag_text(item, "title"),
                url=_rss_link(item),
                summary=_tag_text(item, "description"),
                published_at=parse_datetime(_tag_text(item, "pubDate")),
            )
            if article is not None:
                articles.append(article)

        return articles


class HTMLNewsSource(NewsSourceClient):
    article_selectors: tuple[str, ...] = ()
    title_selectors: tuple[str, ...] = ("a",)
    summary_selectors: tuple[str, ...] = (
        ".summary",
        ".desc",
        ".description",
        "p",
    )
    time_selectors: tuple[str, ...] = ("time", ".date", ".wdate")

    def fetch(self) -> list[NewsArticle]:
        soup = BeautifulSoup(self._request(), "html.parser")
        articles = self._from_json_ld(soup)
        articles.extend(self._from_article_cards(soup))
        articles.extend(self._from_links(soup))
        return unique_articles(articles)[: self.max_items]

    def _from_json_ld(self, soup: BeautifulSoup) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text("", strip=True)
            if not raw:
                continue
            for item in _iter_json_objects(raw):
                article = self._article_from_json(item)
                if article is not None:
                    articles.append(article)
        return articles

    def _article_from_json(self, item: dict[str, Any]) -> NewsArticle | None:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            is_news = any(value in {"NewsArticle", "Article"} for value in item_type)
        else:
            is_news = item_type in {"NewsArticle", "Article"}

        if not is_news:
            return None

        return self._article(
            title=str(item.get("headline") or item.get("name") or ""),
            url=_json_url(item),
            summary=str(item.get("description") or ""),
            published_at=parse_datetime(str(item.get("datePublished") or "")),
        )

    def _from_article_cards(self, soup: BeautifulSoup) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        selectors = self.article_selectors or ("article", "li", "div")

        for selector in selectors:
            for card in soup.select(selector):
                article = self._article_from_card(card)
                if article is not None:
                    articles.append(article)
                if len(articles) >= self.max_items:
                    return articles

        return articles

    def _article_from_card(self, card: Tag) -> NewsArticle | None:
        title_node = _first_select(card, self.title_selectors)
        if title_node is None:
            return None

        href = title_node.get("href") if isinstance(title_node, Tag) else ""
        title = title_node.get_text(" ", strip=True)
        if not href or not _looks_like_news_title(title):
            return None

        summary_node = _first_select(card, self.summary_selectors)
        time_node = _first_select(card, self.time_selectors)

        return self._article(
            title=title,
            url=str(href),
            summary=summary_node.get_text(" ", strip=True) if summary_node else "",
            published_at=parse_datetime(time_node.get_text(" ", strip=True) if time_node else ""),
        )

    def _from_links(self, soup: BeautifulSoup) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        for anchor in soup.find_all("a", href=True):
            title = anchor.get_text(" ", strip=True)
            href = str(anchor.get("href"))
            if not _looks_like_news_title(title):
                continue
            if not self._looks_like_article_url(href):
                continue
            article = self._article(title=title, url=href)
            if article is not None:
                articles.append(article)
            if len(articles) >= self.max_items:
                break
        return articles

    def _looks_like_article_url(self, href: str) -> bool:
        lowered = href.lower()
        return any(token in lowered for token in ("/news", "/article", "/markets", "/business"))


class NaverFinanceNewsSource(HTMLNewsSource):
    article_selectors = (
        "div.mainNewsList li",
        "ul.newsList li",
        "dl.newsList",
        "dd.articleSubject",
        "table.type5 tr",
    )
    title_selectors = (
        "dd.articleSubject a",
        ".articleSubject a",
        "dt a",
        "a",
    )
    summary_selectors = (
        "dd.articleSummary",
        ".articleSummary",
        "p",
    )
    time_selectors = (".wdate", ".date")

    def fetch(self) -> list[NewsArticle]:
        try:
            articles = super().fetch()
        except requests.RequestException:
            articles = []

        if articles or not self.source.url.endswith("mainnews.naver"):
            return articles

        alternate = replace(
            self.source,
            url=self.source.url.replace("mainnews.naver", "mainnews.nhn"),
        )
        return NaverFinanceNewsSource(alternate, self.max_items).fetch()

    def _looks_like_article_url(self, href: str) -> bool:
        return "/news/" in href or "article_id=" in href or "office_id=" in href


class NaverStockNewsSource(HTMLNewsSource):
    article_selectors = (
        "article",
        "li",
        "div[class*=News]",
        "div[class*=news]",
    )

    def _looks_like_article_url(self, href: str) -> bool:
        return "/news" in href.lower() or "article" in href.lower()


class YahooFinanceNewsSource(RSSNewsSource):
    def fetch(self) -> list[NewsArticle]:
        try:
            articles = super().fetch()
        except requests.RequestException:
            articles = []
        if articles:
            return articles

        alternate = replace(self.source, url="https://finance.yahoo.com/news", method="html")
        return YahooFinanceHTMLNewsSource(alternate, self.max_items).fetch()


class YahooFinanceHTMLNewsSource(HTMLNewsSource):
    article_selectors = (
        "article",
        "li",
        "div[class*=story]",
        "div[class*=Story]",
        "section li",
    )

    def _looks_like_article_url(self, href: str) -> bool:
        lowered = href.lower()
        return "/news/" in lowered or "/video/" in lowered


class ReutersNewsSource(HTMLNewsSource):
    article_selectors = (
        "article",
        "li",
        "div[data-testid*=StoryCard]",
        "div[class*=story]",
        "div[class*=media-story-card]",
    )

    def _looks_like_article_url(self, href: str) -> bool:
        lowered = href.lower()
        return lowered.startswith("/markets") or lowered.startswith("/business") or "/markets/" in lowered


class CNBCNewsSource(RSSNewsSource):
    def fetch(self) -> list[NewsArticle]:
        try:
            articles = super().fetch()
        except requests.RequestException:
            articles = []
        if articles:
            return articles

        alternate = replace(self.source, url="https://www.cnbc.com/markets/", method="html")
        return CNBCHTMLNewsSource(alternate, self.max_items).fetch()


class CNBCHTMLNewsSource(HTMLNewsSource):
    article_selectors = (
        "article",
        "li",
        "div.Card-titleContainer",
        "div[class*=Card]",
        "div[class*=LatestNews]",
    )

    def _looks_like_article_url(self, href: str) -> bool:
        lowered = href.lower()
        return "/20" in lowered or "/markets/" in lowered or "/finance/" in lowered


def build_news_source_client(source: NewsSourceConfig, max_items: int) -> NewsSourceClient:
    provider = source.provider.lower()
    if provider == "naver_finance":
        return NaverFinanceNewsSource(source, max_items)
    if provider == "naver_stock":
        return NaverStockNewsSource(source, max_items)
    if provider == "yahoo_finance":
        return YahooFinanceNewsSource(source, max_items)
    if provider == "reuters":
        return ReutersNewsSource(source, max_items)
    if provider == "cnbc":
        return CNBCNewsSource(source, max_items)
    if source.method.lower() == "html":
        return HTMLNewsSource(source, max_items)
    return RSSNewsSource(source, max_items)


def unique_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    result: list[NewsArticle] = []
    for article in articles:
        key = article.url.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result


def clean_text(value: str) -> str:
    cleaned = html.unescape(value or "")
    cleaned = BeautifulSoup(cleaned, "html.parser").get_text(" ", strip=True)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_datetime(value: str) -> datetime | None:
    value = clean_text(value)
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        pass

    normalized = value.replace("오전", "AM").replace("오후", "PM")
    normalized = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in (
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d %p %I:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _tag_text(item: Tag, tag_name: str) -> str:
    tag = item.find(tag_name) or item.find(tag_name.lower())
    if tag is None or tag.text is None:
        return ""
    return tag.text.strip()


def _rss_link(item: Tag) -> str:
    link = _tag_text(item, "link")
    if link:
        return link

    description = _tag_text(item, "description")
    description_soup = BeautifulSoup(description, "html.parser")

    for anchor in description_soup.find_all("a", href=True):
        return str(anchor.get("href")).strip()

    guid = _tag_text(item, "guid")
    return guid


def _first_select(node: Tag, selectors: tuple[str, ...]) -> Tag | None:
    for selector in selectors:
        selected = node.select_one(selector)
        if selected is not None:
            return selected
    return None


def _looks_like_news_title(title: str) -> bool:
    normalized = clean_text(title).lower()
    if len(normalized) < 8:
        return False
    return any(keyword in normalized for keyword in MARKET_KEYWORDS)


def _json_url(item: dict[str, Any]) -> str:
    value = item.get("url")
    if isinstance(value, str):
        return value

    main_entity = item.get("mainEntityOfPage")
    if isinstance(main_entity, str):
        return main_entity
    if isinstance(main_entity, dict):
        url = main_entity.get("@id") or main_entity.get("url")
        if isinstance(url, str):
            return url

    return ""


def _iter_json_objects(raw: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []

    objects: list[dict[str, Any]] = []
    stack = parsed if isinstance(parsed, list) else [parsed]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            objects.append(item)
            for value in item.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return objects
