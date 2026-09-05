"""
Finni LLM Scorer — Sentiment scoring via Groq (primary) + Google Gemini (fallback).

Design choices:
- Single-pass structured JSON prompt: sentiment score, label, reasoning, spillover, event type
- Groq llama-3.1-8b-instant as primary (fast, 14,400 req/day free)
- Gemini 2.0 Flash as fallback on 429/5xx errors
- AsyncIO rate limiter to stay well under RPM limits
- Robust JSON parsing with fallback extraction
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import (
    BATCH_SUMMARY_CHARS,
    CompanyConfig,
    LLM_PROVIDER_ORDER,
    GROQ_MAX_RPM,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_REASONING_EFFORT,
    GROQ_REASONING_FORMAT,
    GROQ_TEMPERATURE,
    GEMINI_MAX_RPM,
    GEMINI_MAX_TOKENS,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    get_gemini_api_key,
    get_groq_api_key,
    TICKER_TO_COMPANY,
)
from src.news_fetcher import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Structured sentiment output from LLM scoring."""
    article_title: str
    article_url: str
    article_source: str
    article_published_at: datetime
    sentiment_score: float              # -1.0 to +1.0
    sentiment_label: str                # VERY_BEARISH to VERY_BULLISH
    confidence: float                   # 0.0 to 1.0
    impact_magnitude: str               # HIGH, MEDIUM, LOW
    reasoning: str                      # 1-2 sentence explanation
    sector_spillover: str | None        # Spillover note or None
    affected_tickers: list[str] = field(default_factory=list)
    event_type: str = "OTHER"           # EARNINGS, REGULATORY, MACRO, etc.
    provider_used: str = "groq"         # which LLM provider served this


class RateLimiter:
    """Simple async rate limiter using a token bucket approach."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self._last_call + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_call = asyncio.get_event_loop().time()


# ──────────────────────────────────────────────
# Prompt Template
# ──────────────────────────────────────────────

SENTIMENT_PROMPT_TEMPLATE = """You are an Indian stock market analyst. Analyze this news article for its impact on {company_name} ({ticker}), which operates in the {sector} / {sub_sector} sector.

ARTICLE:
Title: {title}
Source: {source}
Published: {published}
Summary: {summary}

CONTEXT:
- Company: {company_name} ({ticker})
- Sector: {sector} → {sub_sector}
- Peer companies in our watchlist: {peers}
- Current date: {current_date}

Respond ONLY with valid JSON format (no markdown fences, no extra text):
{{"sentiment_score": <float from -1.0 to +1.0>, "sentiment_label": "<VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH>", "confidence": <float 0.0 to 1.0>, "impact_magnitude": "<HIGH|MEDIUM|LOW>", "reasoning": "<1-2 sentence explanation>", "sector_spillover": <null or "brief note">, "affected_tickers": [<list of tickers from watchlist>], "event_type": "<EARNINGS|REGULATORY|MACRO|PRODUCT|MANAGEMENT|LEGAL|SECTOR_TREND|MARKET_SENTIMENT|OTHER>"}}

CALIBRATION ANCHORS:
- +1.0: Massive positive catalyst (huge earnings beat, major contract win)
- +0.5: Positive news (upgrade, solid product launch, good quarter)
- +0.1: Mildly positive, routine positive mention
-  0.0: Factual, purely macro without specific company impact, or unrelated
- -0.5: Negative news (downgrade, earnings miss, executive exit)
- -1.0: Major crisis (fraud, massive lawsuit, bankruptcy risk)
"""


# Batched variant: every article for one company scored in a SINGLE request.
# One call per company instead of one per article cuts request count ~8x and
# token use even further, since the preamble is sent once rather than per article.
SENTIMENT_BATCH_PROMPT_TEMPLATE = """You are an Indian stock market analyst. Analyze EACH numbered news article below for its impact on {company_name} ({ticker}), which operates in the {sector} / {sub_sector} sector. Today is {current_date}.

ARTICLES:
{articles_block}

Respond ONLY with a valid JSON array — exactly one object per article, in the same order, reusing each article's "id" (no markdown fences, no extra text):
[{{"id": <int>, "sentiment_score": <float from -1.0 to +1.0>, "sentiment_label": "<VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH>", "confidence": <float 0.0 to 1.0>, "impact_magnitude": "<HIGH|MEDIUM|LOW>", "reasoning": "<1-2 sentence explanation>", "sector_spillover": <null or "brief note">, "event_type": "<EARNINGS|REGULATORY|MACRO|PRODUCT|MANAGEMENT|LEGAL|SECTOR_TREND|MARKET_SENTIMENT|OTHER>"}}]

Write every number as a plain numeral (0.9, never "0. nine").

CALIBRATION ANCHORS:
- +1.0: Massive positive catalyst (huge earnings beat, major contract win)
- +0.5: Positive news (upgrade, solid product launch, good quarter)
- +0.1: Mildly positive, routine positive mention
-  0.0: Factual, purely macro without specific company impact, or unrelated
- -0.5: Negative news (downgrade, earnings miss, executive exit)
- -1.0: Major crisis (fraud, massive lawsuit, bankruptcy risk)
"""


class LLMScorer:
    """Scores news articles for sentiment using LLM APIs."""

    def __init__(self):
        self._groq_client = None
        self._gemini_model = None
        self.groq_limiter = RateLimiter(GROQ_MAX_RPM)
        self.gemini_limiter = RateLimiter(GEMINI_MAX_RPM)
        self._groq_available = True
        self._gemini_available = True

    def _get_groq_client(self):
        """Lazy-init Groq client."""
        if self._groq_client is None:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=get_groq_api_key())
            except Exception as e:
                logger.warning(f"Groq client init failed: {e}")
                self._groq_available = False
        return self._groq_client

    def _get_gemini_model(self):
        """Lazy-init Gemini client."""
        if self._gemini_model is None:
            try:
                from google import genai
                client = genai.Client(api_key=get_gemini_api_key())
                self._gemini_model = client
            except Exception as e:
                logger.warning(f"Gemini client init failed: {e}")
                self._gemini_available = False
        return self._gemini_model

    async def score_batch(
        self,
        articles: list[NewsArticle],
        company: CompanyConfig,
    ) -> list[SentimentResult]:
        """
        Score every article for one company in a SINGLE LLM call.

        Scoring one article per request meant 350+ requests a day, which blew
        through the provider's daily token allowance before the run finished —
        the preamble alone was re-sent with every article. Batching sends it once.
        Falls back to per-article calls only if the batch response can't be used.
        """
        if not articles:
            return []

        prompt = self._build_batch_prompt(articles, company)
        result = await self.complete_json(prompt, expect_array=True)

        if result is not None:
            parsed, provider = result
            scored = self._build_batch_results(parsed, articles, provider)
            if scored is not None:
                return scored
            logger.warning(
                f"{company.short_name}: batch response did not cover all "
                f"{len(articles)} articles — falling back to per-article scoring"
            )
        else:
            logger.warning(
                f"{company.short_name}: batch scoring failed — falling back to per-article"
            )

        # Fallback: original one-call-per-article path.
        results = []
        for article in articles:
            try:
                results.append(await self.score_article(article, company))
            except Exception as e:
                logger.error(f"Failed to score article '{article.title[:60]}...': {e}")
                results.append(self._neutral_fallback(article))
        return results

    def _build_batch_prompt(
        self, articles: list[NewsArticle], company: CompanyConfig
    ) -> str:
        """Render all of a company's articles into one numbered prompt."""
        blocks = []
        for i, article in enumerate(articles, 1):
            summary = (article.summary or "(no summary)")[:BATCH_SUMMARY_CHARS]
            blocks.append(
                f"[{i}] Title: {article.title}\n"
                f"    Source: {article.source} | Published: "
                f"{article.published_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"    Summary: {summary}"
            )

        return SENTIMENT_BATCH_PROMPT_TEMPLATE.format(
            company_name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            sub_sector=company.sub_sector,
            current_date=datetime.now().strftime("%Y-%m-%d"),
            articles_block="\n\n".join(blocks),
        )

    def _build_batch_results(
        self, parsed: object, articles: list[NewsArticle], provider: str
    ) -> list[SentimentResult] | None:
        """
        Map a parsed JSON array back onto the articles it scored.

        Returns None if the response can't be matched up, so the caller can retry
        per-article rather than silently emitting neutral scores.
        """
        if not isinstance(parsed, list) or not parsed:
            return None

        # Prefer the model's own "id" field; fall back to positional order.
        by_id: dict[int, dict] = {}
        for pos, item in enumerate(parsed, 1):
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("id", pos))
            except (TypeError, ValueError):
                idx = pos
            by_id.setdefault(idx, item)

        if len(by_id) < len(articles):
            return None

        results = []
        for i, article in enumerate(articles, 1):
            item = by_id.get(i)
            if item is None:
                return None
            try:
                results.append(self._build_result(item, article, provider=provider))
            except Exception as e:
                logger.warning(f"Malformed entry for article {i}: {e}")
                results.append(self._neutral_fallback(article))
        return results

    async def complete_json(
        self, prompt: str, expect_array: bool = False
    ) -> tuple[dict | list, str] | None:
        """
        Send a prompt to the configured providers in order and return the first
        successfully parsed JSON response as (parsed, provider_name).

        Set expect_array=True when the prompt asks for a JSON array (batch scoring).
        Returns None if every provider failed. Shared by article scoring and the
        sector pattern analyzer so both honour the same order and rate limiters.
        """
        for provider in LLM_PROVIDER_ORDER:
            if provider == "groq":
                available, limiter, call = self._groq_available, self.groq_limiter, self._call_groq
            elif provider == "gemini":
                available, limiter, call = self._gemini_available, self.gemini_limiter, self._call_gemini
            else:
                logger.warning(f"Unknown LLM provider in LLM_PROVIDER_ORDER: {provider}")
                continue

            if not available:
                continue

            try:
                await limiter.acquire()
                response_text = await call(prompt)
            except Exception as e:
                logger.warning(f"{provider} API call failed: {e}")
                continue

            try:
                return self._parse_response(response_text, expect_array), provider
            except Exception as e:
                logger.warning(f"{provider} parsing failed: {e}. Raw response: {response_text[:300]}")

        return None

    async def score_article(
        self,
        article: NewsArticle,
        company: CompanyConfig,
    ) -> SentimentResult:
        """
        Score a single article, trying each provider in LLM_PROVIDER_ORDER.
        """
        prompt = self._build_prompt(article, company)

        result = await self.complete_json(prompt)
        if result is not None:
            parsed, provider = result
            if isinstance(parsed, dict):
                return self._build_result(parsed, article, provider=provider)
            logger.warning(f"{provider} returned a non-object for a single article")

        # Every provider failed — return neutral fallback
        logger.error(f"All LLM providers failed for: {article.title[:60]}")
        return self._neutral_fallback(article)

    def _build_prompt(self, article: NewsArticle, company: CompanyConfig) -> str:
        """Build the scoring prompt for an article + company pair."""
        # Build peer list string
        peer_names = []
        for peer_ticker in company.peers:
            peer = TICKER_TO_COMPANY.get(peer_ticker)
            if peer:
                peer_names.append(f"{peer.short_name} ({peer.ticker})")
        peers_str = ", ".join(peer_names) if peer_names else "None in watchlist"

        return SENTIMENT_PROMPT_TEMPLATE.format(
            company_name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            sub_sector=company.sub_sector,
            title=article.title,
            source=article.source,
            published=article.published_at.strftime("%Y-%m-%d %H:%M"),
            summary=article.summary[:400] if article.summary else "(no summary)",
            peers=peers_str,
            current_date=datetime.now().strftime("%Y-%m-%d"),
        )

    async def _call_groq(self, prompt: str) -> str:
        """Call Groq API synchronously (wrapped in executor for async compat)."""
        client = self._get_groq_client()
        if client is None:
            raise RuntimeError("Groq client not available")

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial sentiment analyst. Respond only with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=GROQ_TEMPERATURE,
                max_tokens=GROQ_MAX_TOKENS,
                reasoning_effort=GROQ_REASONING_EFFORT,
                reasoning_format=GROQ_REASONING_FORMAT,
            ),
        )
        return response.choices[0].message.content

    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API via REST to bypass SDK API key format bugs."""
        api_key = get_gemini_api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": GEMINI_TEMPERATURE,
                "maxOutputTokens": GEMINI_MAX_TOKENS,
                "responseMimeType": "application/json"
            }
        }
        
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Gemini REST API failed ({response.status}): {error_text}")
                data = await response.json()
                
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Malformed Gemini response: {data}") from e

    # Models occasionally spell a decimal out mid-number ("confidence": 0. nine),
    # which is not valid JSON and killed otherwise-good responses.
    _SPELLED_DIGITS = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    }

    @classmethod
    def _repair_spelled_decimals(cls, text: str) -> str:
        """Turn `0. nine` into `0.9`. No-op when the JSON is already clean."""
        pattern = re.compile(
            r"(\d)\.\s*(" + "|".join(cls._SPELLED_DIGITS) + r")\b", re.IGNORECASE
        )
        return pattern.sub(
            lambda m: f"{m.group(1)}.{cls._SPELLED_DIGITS[m.group(2).lower()]}", text
        )

    def _parse_response(self, response_text: str, expect_array: bool = False) -> dict | list:
        """
        Parse an LLM response into a dict (or a list when expect_array is set).
        Handles markdown fences, surrounding prose, and spelled-out decimals.
        """
        if not response_text:
            raise ValueError("Empty response from LLM")

        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrapper
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        cleaned = self._repair_spelled_decimals(cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Fall back to carving the JSON out of surrounding prose.
        patterns = [r"\[.*\]", r"\{.*\}"] if expect_array else [r"\{.*\}", r"\[.*\]"]
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue

        raise ValueError(f"Could not parse LLM response as JSON: {cleaned[:200]}")

    def _build_result(
        self, parsed: dict, article: NewsArticle, provider: str
    ) -> SentimentResult:
        """Build a SentimentResult from parsed LLM JSON output."""
        return SentimentResult(
            article_title=article.title,
            article_url=article.url,
            article_source=article.source,
            article_published_at=article.published_at,
            sentiment_score=self._clamp(float(parsed.get("sentiment_score") or 0.0), -1.0, 1.0),
            sentiment_label=parsed.get("sentiment_label", "NEUTRAL"),
            confidence=self._clamp(float(parsed.get("confidence") or 0.5), 0.0, 1.0),
            impact_magnitude=parsed.get("impact_magnitude", "MEDIUM"),
            reasoning=parsed.get("reasoning", "No reasoning provided."),
            sector_spillover=parsed.get("sector_spillover"),
            affected_tickers=parsed.get("affected_tickers", []),
            event_type=parsed.get("event_type", "OTHER"),
            provider_used=provider,
        )

    def _neutral_fallback(self, article: NewsArticle) -> SentimentResult:
        """Create a neutral-scored fallback when LLM scoring fails entirely."""
        return SentimentResult(
            article_title=article.title,
            article_url=article.url,
            article_source=article.source,
            article_published_at=article.published_at,
            sentiment_score=0.0,
            sentiment_label="NEUTRAL",
            confidence=0.1,
            impact_magnitude="LOW",
            reasoning="LLM scoring failed — defaulting to neutral.",
            sector_spillover=None,
            affected_tickers=[],
            event_type="OTHER",
            provider_used="fallback",
        )

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
