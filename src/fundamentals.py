"""
Finni Fundamentals — Valuation and quality metrics scraped from screener.in.

Screener.in serves a company page per NSE symbol (screener.in/company/TCS/) with a
"top ratios" block holding P/E, ROCE, ROE, dividend yield, market cap and book value.
No login or API key is needed for that block, and the URL keys off the bare NSE
symbol, so it maps directly onto the tickers already in config.

This is a third, slower-moving signal alongside news sentiment and technicals: it
says whether a stock is cheap or expensive and how well it earns on capital, which
neither of the other two capture. It is deliberately NOT part of the blended signal
score — it is reported for context so a bearish technical read on a high-ROCE,
low-P/E company reads differently from the same read on an expensive one.

Everything here fails soft: a miss returns None and the pipeline carries on.
"""

import logging
import re

import aiohttp
from bs4 import BeautifulSoup

from src.config import (
    SCREENER_SEARCH_URL,
    SCREENER_SYMBOL_OVERRIDES,
    SCREENER_TIMEOUT_SECONDS,
    SCREENER_URL_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Browser UA — screener.in serves a trimmed page to obvious bots.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# Screener's label -> our field name. Labels are matched case-insensitively on a
# normalised (whitespace-collapsed) string, so "Stock P/E" survives markup changes.
_RATIO_FIELDS = {
    "market cap": "market_cap",
    "current price": "current_price",
    "stock p/e": "pe_ratio",
    "book value": "book_value",
    "dividend yield": "dividend_yield",
    "roce": "roce",
    "roe": "roe",
    "face value": "face_value",
}


def _clean_number(raw: str) -> float | None:
    """
    Pull a float out of screener's display strings.

    Handles the rupee sign, Indian comma grouping, percent signs and the "Cr."
    suffix: "₹17,89,001Cr." -> 1789001.0, "7.78%" -> 7.78, "45.6" -> 45.6.
    Ranges like "₹1,612/1,250" (High/Low) return the first value.
    """
    if not raw:
        return None
    text = raw.split("/")[0]
    text = re.sub(r"[₹,%]", "", text)
    text = re.sub(r"(?i)\bcr\.?", "", text)
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


class FundamentalsFetcher:
    """Fetches per-company valuation ratios from screener.in."""

    def screener_symbol(self, ticker: str) -> str:
        """Map a yfinance ticker onto screener.in's URL symbol."""
        symbol = ticker.replace(".NS", "")
        return SCREENER_SYMBOL_OVERRIDES.get(symbol, symbol)

    async def _get_html(
        self, session: aiohttp.ClientSession, url: str
    ) -> str | None:
        """GET a screener page, returning None on any non-200 or transport error."""
        try:
            async with session.get(
                url,
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=SCREENER_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.text()
        except Exception as e:
            logger.debug(f"screener.in GET failed for {url}: {e}")
            return None

    async def _resolve_via_search(
        self, session: aiohttp.ClientSession, company_name: str
    ) -> str | None:
        """
        Look a company up by name via screener's search endpoint.

        Used when the bare NSE symbol 404s — screener lists some companies under a
        different symbol, and searching the full name resolves those without us
        hand-maintaining a mapping. Returns an absolute company URL, or None.
        """
        try:
            async with session.get(
                SCREENER_SEARCH_URL,
                params={"q": company_name},
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=SCREENER_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    return None
                hits = await resp.json(content_type=None)
        except Exception as e:
            logger.debug(f"screener.in search failed for {company_name!r}: {e}")
            return None

        if not isinstance(hits, list) or not hits:
            return None

        path = (hits[0] or {}).get("url")
        if not path:
            return None
        return f"https://www.screener.in{path}"

    async def fetch(
        self,
        session: aiohttp.ClientSession,
        ticker: str,
        company_name: str | None = None,
    ) -> dict[str, float] | None:
        """
        Fetch the ratio block for one ticker.

        Tries the bare NSE symbol first, then falls back to screener's own search
        using the company name. Returns metric -> value, or None if neither
        resolves (logged, never fatal).
        """
        symbol = self.screener_symbol(ticker)
        html = await self._get_html(session, SCREENER_URL_TEMPLATE.format(symbol=symbol))

        if html is None and company_name:
            url = await self._resolve_via_search(session, company_name)
            if url:
                logger.info(f"screener.in: resolved {symbol} via search -> {url}")
                html = await self._get_html(session, url)

        if html is None:
            logger.warning(f"screener.in has no usable page for {symbol}")
            return None

        return self._parse_ratios(html, symbol)

    def _parse_ratios(self, html: str, symbol: str) -> dict[str, float] | None:
        """Extract the #top-ratios list into a flat metric dict."""
        try:
            block = BeautifulSoup(html, "html.parser").find("ul", id="top-ratios")
        except Exception as e:
            logger.warning(f"screener.in parse failed for {symbol}: {e}")
            return None

        if block is None:
            logger.warning(f"screener.in page for {symbol} had no top-ratios block")
            return None

        ratios: dict[str, float] = {}
        for item in block.find_all("li"):
            name_el = item.find("span", class_="name")
            value_el = item.find("span", class_="value")
            if not name_el or not value_el:
                continue

            label = " ".join(name_el.get_text(strip=True).split()).lower()
            field = _RATIO_FIELDS.get(label)
            if field is None:
                continue

            value = _clean_number(" ".join(value_el.get_text(strip=True).split()))
            if value is not None:
                ratios[field] = value

        if not ratios:
            logger.warning(f"screener.in returned no recognised ratios for {symbol}")
            return None

        return ratios

    async def fetch_all(
        self, tickers: list[str], names: dict[str, str] | None = None
    ) -> dict[str, dict[str, float]]:
        """
        Fetch fundamentals for every ticker, sequentially and politely.

        Screener is a free site being scraped, so this stays serial rather than
        firing 49 concurrent requests at it. It is fast anyway: no LLM in the loop.
        """
        results: dict[str, dict[str, float]] = {}
        async with aiohttp.ClientSession() as session:
            for ticker in tickers:
                data = await self.fetch(
                    session, ticker, (names or {}).get(ticker)
                )
                if data:
                    results[ticker] = data
        return results
