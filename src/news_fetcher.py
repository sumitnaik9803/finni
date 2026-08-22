"""
Finni News Fetcher — RSS-based news ingestion with deduplication and company mapping.

Sources:
- Economic Times Markets & Business RSS
- Business Standard Markets RSS
- LiveMint Markets RSS
- Google News RSS (per-company search)

Design choices:
- RSS-only (no full-article scraping) for reliability and speed
- 18-hour news window to capture post-market + overnight + early AM news
- Fuzzy title deduplication to handle cross-source reposts
- Keyword-based company mapping using config taxonomy
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import quote_plus

import aiohttp
import feedparser
from dateutil import parser as date_parser

from src.config import (
    COMPANIES,
    CompanyConfig,
    GOOGLE_NEWS_RSS_TEMPLATE,
    NEWS_SOURCES,
    NEWS_WINDOW_HOURS,
    NewsSourceConfig,
)

logger = logging.getLogger(__name__)

# Indian Standard Time offset
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class NewsArticle:
    """A single news article from RSS."""
    title: str
    url: str
    source: str                          # e.g., "Economic Times Markets"
    source_tier: int                     # 1, 2, or 3
    published_at: datetime
    summary: str                         # RSS description/snippet
    matched_tickers: list[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        if not isinstance(other, NewsArticle):
            return NotImplemented
        return self.url == other.url


class NewsFetcher:
    """Fetches and processes news from multiple RSS sources."""

    def __init__(self, news_window_hours: int = NEWS_WINDOW_HOURS):
        self.news_window_hours = news_window_hours
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(hours=news_window_hours)

    async def fetch_all(self, companies: list[CompanyConfig] | None = None) -> dict[str, list[NewsArticle]]:
        """
        Fetch news from all sources and map to companies.

        Returns:
            dict mapping ticker -> list of relevant NewsArticle objects
        """
        if companies is None:
            companies = COMPANIES

        all_articles: list[NewsArticle] = []

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Finni-StockBot/1.0 (RSS Reader)"},
        ) as session:
            # 1. Fetch all general market RSS feeds concurrently
            general_tasks = [
                self._fetch_rss_feed(session, source)
                for source in NEWS_SOURCES
            ]

            # 2. Fetch company-specific Google News RSS feeds concurrently
            google_tasks = [
                self._fetch_google_news(session, company)
                for company in companies
            ]

            # Gather all results
            results = await asyncio.gather(
                *general_tasks, *google_tasks,
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Feed fetch failed: {result}")
                    continue
                all_articles.extend(result)

        logger.info(f"Raw articles fetched: {len(all_articles)}")

        # 3. Deduplicate by URL and fuzzy title matching
        deduped = self._deduplicate(all_articles)
        logger.info(f"After deduplication: {len(deduped)}")

        # 4. Map articles to companies using keyword matching
        mapped = self._map_to_companies(deduped, companies)

        # Log per-company counts
        for ticker, articles in mapped.items():
            logger.info(f"  {ticker}: {len(articles)} articles")

        return mapped

    async def _fetch_rss_feed(
        self, session: aiohttp.ClientSession, source: NewsSourceConfig
    ) -> list[NewsArticle]:
        """Fetch and parse a single RSS feed."""
        try:
            async with session.get(source.url) as resp:
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} from {source.name}: {source.url}")
                    return []
                content = await resp.text()
        except Exception as e:
            logger.warning(f"Failed to fetch {source.name}: {e}")
            return []

        feed = feedparser.parse(content)
        articles = []

        for entry in feed.entries:
            article = self._parse_entry(entry, source.name, source.tier)
            if article and article.published_at >= self.cutoff_time:
                articles.append(article)

        logger.debug(f"  {source.name}: {len(articles)} articles within window")
        return articles

    async def _fetch_google_news(
        self, session: aiohttp.ClientSession, company: CompanyConfig
    ) -> list[NewsArticle]:
        """Fetch Google News RSS for a specific company."""
        query = quote_plus(f"{company.short_name} {company.ticker.replace('.NS', '')}")
        url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=query)

        source_config = NewsSourceConfig(
            name=f"Google News ({company.short_name})",
            url=url,
            tier=2,
            category="company_specific",
        )

        articles = await self._fetch_rss_feed(session, source_config)

        # Pre-tag these articles with the company ticker since they're from a
        # company-specific search
        for article in articles:
            if company.ticker not in article.matched_tickers:
                article.matched_tickers.append(company.ticker)

        return articles

    def _parse_entry(self, entry: dict, source_name: str, source_tier: int) -> NewsArticle | None:
        """Parse a single feedparser entry into a NewsArticle."""
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Parse URL
        url = entry.get("link", "").strip()
        if not url:
            return None

        # Parse published date
        published_at = self._parse_date(entry)
        if published_at is None:
            # If no date available, assume it's recent (within the last hour)
            published_at = datetime.now(timezone.utc) - timedelta(minutes=30)

        # Parse summary/description
        summary = entry.get("summary", entry.get("description", "")).strip()
        # Clean HTML tags from summary
        summary = self._strip_html(summary)
        # Truncate overly long summaries
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return NewsArticle(
            title=title,
            url=url,
            source=source_name,
            source_tier=source_tier,
            published_at=published_at,
            summary=summary,
        )

    def _parse_date(self, entry: dict) -> datetime | None:
        """Extract and parse published date from a feed entry."""
        # feedparser often pre-parses dates into published_parsed
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            try:
                dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                return dt
            except (OverflowError, ValueError, OSError):
                pass

        # Try raw date strings
        for date_field in ("published", "updated", "created"):
            raw = entry.get(date_field, "")
            if raw:
                try:
                    return date_parser.parse(raw, fuzzy=True).astimezone(timezone.utc)
                except (ValueError, OverflowError):
                    continue

        return None

    def _deduplicate(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """
        Remove duplicate articles using:
        1. Exact URL dedup
        2. Fuzzy title matching (>85% similarity = duplicate)
        """
        # Step 1: URL dedup
        seen_urls: set[str] = set()
        url_deduped: list[NewsArticle] = []
        for article in articles:
            normalized_url = article.url.split("?")[0].rstrip("/").lower()
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                url_deduped.append(article)

        # Step 2: Fuzzy title dedup — keep the article from the higher-tier source
        final: list[NewsArticle] = []
        for article in url_deduped:
            is_dup = False
            for existing in final:
                similarity = SequenceMatcher(
                    None,
                    article.title.lower(),
                    existing.title.lower(),
                ).ratio()
                if similarity > 0.85:
                    # Keep the one from the better (lower-numbered) tier
                    if article.source_tier < existing.source_tier:
                        final.remove(existing)
                        final.append(article)
                    is_dup = True
                    break
            if not is_dup:
                final.append(article)

        return final

    def _map_to_companies(
        self,
        articles: list[NewsArticle],
        companies: list[CompanyConfig],
    ) -> dict[str, list[NewsArticle]]:
        """
        Map articles to companies using keyword matching.

        An article can map to multiple companies (e.g., sector-wide news).
        """
        result: dict[str, list[NewsArticle]] = {c.ticker: [] for c in companies}

        for article in articles:
            searchable = f"{article.title} {article.summary}".lower()

            for company in companies:
                # Check if already pre-tagged (e.g., from Google News search)
                if company.ticker in article.matched_tickers:
                    if article not in result[company.ticker]:
                        result[company.ticker].append(article)
                    continue

                # Keyword matching — use word-boundary regex for short keywords
                # to prevent false positives (e.g., 'itc' matching 'critical')
                for keyword in company.keywords:
                    kw = keyword.lower()
                    if len(kw) <= 4:
                        # Short keywords need word-boundary matching
                        if re.search(r'\b' + re.escape(kw) + r'\b', searchable):
                            matched = True
                        else:
                            matched = False
                    else:
                        matched = kw in searchable

                    if matched:
                        if company.ticker not in article.matched_tickers:
                            article.matched_tickers.append(company.ticker)
                        if article not in result[company.ticker]:
                            result[company.ticker].append(article)
                        break  # One keyword match is enough for this company

        return result

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from text. Simple regex-free approach."""
        result = []
        in_tag = False
        for char in text:
            if char == "<":
                in_tag = True
            elif char == ">":
                in_tag = False
            elif not in_tag:
                result.append(char)
        return "".join(result).strip()
