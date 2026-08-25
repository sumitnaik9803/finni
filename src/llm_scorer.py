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
    CompanyConfig,
    GROQ_MAX_RPM,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
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
        """Score a batch of articles for a single company."""
        results = []
        for article in articles:
            try:
                result = await self.score_article(article, company)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to score article '{article.title[:60]}...': {e}")
                # Create a neutral fallback result so the pipeline doesn't break
                results.append(self._neutral_fallback(article))
        return results

    async def score_article(
        self,
        article: NewsArticle,
        company: CompanyConfig,
    ) -> SentimentResult:
        """
        Score a single article. Tries Groq first, falls back to Gemini.
        """
        prompt = self._build_prompt(article, company)

        # Try Groq first
        if self._groq_available:
            try:
                await self.groq_limiter.acquire()
                response_text = await self._call_groq(prompt)
                try:
                    parsed = self._parse_response(response_text)
                    return self._build_result(parsed, article, provider="groq")
                except Exception as e:
                    logger.warning(f"Groq parsing failed: {e}. Raw response: {response_text[:300]}")
            except Exception as e:
                logger.warning(f"Groq API call failed: {e} — falling back to Gemini")

        # Fallback to Gemini
        if self._gemini_available:
            try:
                await self.gemini_limiter.acquire()
                response_text = await self._call_gemini(prompt)
                try:
                    parsed = self._parse_response(response_text)
                    return self._build_result(parsed, article, provider="gemini")
                except Exception as e:
                    logger.error(f"Gemini parsing failed: {e}. Raw response: {response_text[:300]}")
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")

        # Both failed — return neutral fallback
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
                response_format={"type": "json_object"},
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

    def _parse_response(self, response_text: str) -> dict:
        """
        Parse LLM response into a dict. Handles common issues:
        - Markdown fences around JSON
        - Partial/malformed JSON
        """
        if not response_text:
            raise ValueError("Empty response from LLM")

        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrapper
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
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
