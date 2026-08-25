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
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
        # Determine window based on day of week (Monday = 66 hours to cover weekend)
        now = datetime.now(timezone.utc)
        hours = 66 if now.weekday() == 0 else NEWS_WINDOW_HOURS
        self.cutoff_time = now - timedelta(hours=hours)

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
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _fetch_rss_feed(
        self, session: aiohttp.ClientSession, source: NewsSourceConfig
    ) -> list[NewsArticle]:
        """Fetch and parse a single RSS feed with retry logic."""
        async with session.get(source.url) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status} from {source.name}: {source.url}")
            
            # Read bytes directly and decode manually to handle bad characters (like Windows-1252 smart quotes)
            raw_bytes = await resp.read()
            content = raw_bytes.decode('utf-8', errors='replace')

        feed = feedparser.parse(content)
        articles = []

        for entry in feed.entries:
            article = self._parse_entry(entry, source.name, source.tier)
            if article and article.published_at >= self.cutoff_time:
                # Enrich summary if it is thin (< 50 chars)
                if len(article.summary) < 50:
                    try:
                        desc = await self._fetch_og_description(session, article.url)
                        if desc:
                            article.summary = desc
                    except Exception as e:
                        logger.debug(f"Failed to fetch og:description for {article.url}: {e}")
                articles.append(article)

        logger.debug(f"  {source.name}: {len(articles)} articles within window")
        return articles

    async def _fetch_og_description(self, session: aiohttp.ClientSession, url: str) -> str | None:
        """Fetch the OpenGraph description directly from an article's webpage."""
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                meta = soup.find("meta", property="og:description")
                if meta and meta.get("content"):
                    return meta.get("content").strip()
        return None

    async def _fetch_google_news(
        self, session: aiohttp.ClientSession, company: CompanyConfig
    ) -> list[NewsArticle]:
        """Fetch Google News RSS for a specific company using multiple varied queries."""
        # Fire separate queries per company to maximize coverage
        queries = [
            f'"{company.short_name}"',
            f'"{company.short_name}" results',
            f'"{company.short_name}" share',
            f'{company.short_name} stock India' # Unquoted broad fallback
        ]
        
        tasks = []
        for q in queries:
            query_url = quote_plus(q)
            url = GOOGLE_NEWS_RSS_TEMPLATE.format(query=query_url)
            source_config = NewsSourceConfig(
                name=f"Google News ({company.short_name})",
                url=url,
                tier=2,
                category="company_specific",
            )
            # Use gather but catch exceptions so one query failing doesn't kill the others
            tasks.append(self._fetch_rss_feed(session, source_config))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        articles = []
        for result in results:
            if not isinstance(result, Exception):
                articles.extend(result)
        
        # Do NOT pre-tag articles with `matched_tickers` here. They must pass the 
        # standard strict keyword validation in `_map_to_companies` just like ET/Mint feeds
        # to prevent Google's semantic search (e.g. Bitcoin) from causing false positives.
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

        # Limit to the 4 most recent articles per company to avoid LLM rate limits
        for ticker in result:
            articles_list = result[ticker]
            if len(articles_list) > 4:
                # Sort by published_at descending and keep the top 4
                articles_list.sort(key=lambda x: x.published_at, reverse=True)
                result[ticker] = articles_list[:4]

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
