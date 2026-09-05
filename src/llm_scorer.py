"""
Finni LLM Scorer — Sentiment scoring via Groq (primary) + Google Gemini (fallback).

Design choices:
- Single-pass structured JSON prompt: sentiment score, label, reasoning, spillover, event type
- Gemini Flash primary, Groq gpt-oss-120b fallback (see LLM_PROVIDER_ORDER)
- Gemini reached over the Interactions API, since AI Studio now issues only "AQ."
  auth keys and the legacy generateContent endpoint rejects those
- AsyncIO rate limiter to stay well under RPM limits
- Robust JSON parsing with fallback extraction
"""

import asyncio
import json
import logging
import os
import re

import aiohttp
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
    GEMINI_GENERATECONTENT_URL,
    GEMINI_INTERACTIONS_URL,
    GEMINI_MAX_RPM,
    GEMINI_MAX_TOKENS,
    GEMINI_MODEL,
    GEMINI_MODEL_PREFERENCES,
    GEMINI_MODELS_URL,
    GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT_SECONDS,
    GEMINI_USE_INTERACTIONS_API,
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
        self._gemini_surface = None        # "interactions" | "generatecontent", once known
        self._gemini_resolved_model = None  # Set on the first Gemini call of the run

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

    async def _resolve_gemini_model(self, session) -> str:
        """
        Ask the API which models this key can actually use, once per run.

        Free-tier model names turn over fast, and a request naming a retired model
        fails exactly like a bad key, which makes the real problem hard to see. If
        the listing call fails we fall back to the configured GEMINI_MODEL.
        """
        if self._gemini_resolved_model is not None:
            return self._gemini_resolved_model

        self._gemini_resolved_model = GEMINI_MODEL  # Fallback unless listing succeeds.
        try:
            async with session.get(
                GEMINI_MODELS_URL,
                headers={"x-goog-api-key": get_gemini_api_key()},
                timeout=aiohttp.ClientTimeout(total=GEMINI_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Gemini model listing failed ({resp.status}) — "
                        f"using configured {GEMINI_MODEL}"
                    )
                    return self._gemini_resolved_model
                data = await resp.json()
        except Exception as e:
            logger.warning(f"Gemini model listing errored ({e}) — using {GEMINI_MODEL}")
            return self._gemini_resolved_model

        available = {
            (m.get("name") or "").removeprefix("models/")
            for m in data.get("models", [])
        }
        for candidate in GEMINI_MODEL_PREFERENCES:
            if candidate in available:
                self._gemini_resolved_model = candidate
                logger.info(f"Gemini model resolved to {candidate}")
                break
        else:
            logger.warning(
                f"None of {GEMINI_MODEL_PREFERENCES} available to this key "
                f"(saw {len(available)} models) — using {GEMINI_MODEL}"
            )
        return self._gemini_resolved_model

    async def _call_gemini(self, prompt: str) -> str:
        """
        Call Gemini over REST.

        Two surfaces exist and the choice is not cosmetic. AI Studio now issues only
        "AQ." auth keys, and those are documented against the Interactions API; the
        legacy models/{model}:generateContent endpoint rejects them with
        401 ACCESS_TOKEN_TYPE_UNSUPPORTED. Older "AIza" standard keys work on
        generateContent but are themselves being retired. So: try Interactions first,
        fall back to generateContent, and whichever succeeds is remembered for the
        rest of the run so we stop paying for the failed attempt on every call.
        """
        headers = {
            "x-goog-api-key": get_gemini_api_key(),
            "Content-Type": "application/json",
        }
        errors = []

        async with aiohttp.ClientSession() as session:
            model = await self._resolve_gemini_model(session)

            surfaces = ["interactions", "generatecontent"]
            if self._gemini_surface is not None:
                surfaces = [self._gemini_surface]
            elif not GEMINI_USE_INTERACTIONS_API:
                surfaces = ["generatecontent", "interactions"]

            for surface in surfaces:
                url, payload, extract = self._gemini_request(surface, model, prompt)
                try:
                    async with session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=GEMINI_TIMEOUT_SECONDS),
                    ) as response:
                        body = await response.text()
                        if response.status != 200:
                            errors.append(f"{surface} -> {response.status}: {body[:200]}")
                            continue
                        data = json.loads(body)
                except Exception as e:
                    errors.append(f"{surface} -> {e}")
                    continue

                try:
                    text = extract(data)
                except (KeyError, IndexError, TypeError) as e:
                    errors.append(f"{surface} -> malformed response: {e}")
                    continue

                if self._gemini_surface != surface:
                    self._gemini_surface = surface
                    logger.info(f"Gemini responding on the {surface} endpoint")
                return text

        raise RuntimeError("Gemini REST API failed (" + " | ".join(errors) + ")")

    @staticmethod
    def _gemini_request(surface: str, model: str, prompt: str):
        """Build (url, payload, response-extractor) for one Gemini API surface."""
        if surface == "interactions":
            payload = {
                "model": model,
                "input": prompt,
                "generation_config": {
                    "temperature": GEMINI_TEMPERATURE,
                    "max_output_tokens": GEMINI_MAX_TOKENS,
                },
                "response_format": [
                    {"type": "text", "mime_type": "application/json"}
                ],
            }
            return GEMINI_INTERACTIONS_URL, payload, LLMScorer._extract_interactions_text

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": GEMINI_TEMPERATURE,
                "maxOutputTokens": GEMINI_MAX_TOKENS,
                "responseMimeType": "application/json",
            },
        }
        url = GEMINI_GENERATECONTENT_URL.format(model=model)
        return url, payload, LLMScorer._extract_generatecontent_text

    @staticmethod
    def _extract_generatecontent_text(data: dict) -> str:
        return data["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    def _extract_interactions_text(data: dict) -> str:
        """
        Pull the text out of an Interactions response.

        The payload is a `steps` timeline rather than a single candidate, and a step
        can hold several text blocks, so join every text block from the model_output
        steps in order.
        """
        chunks = []
        for step in data.get("steps", []):
            if step.get("type") not in (None, "model_output"):
                continue
            for block in step.get("content", []):
                if block.get("type") == "text" and block.get("text"):
                    chunks.append(block["text"])
        if not chunks:
            raise KeyError(f"no text blocks in interactions response: {str(data)[:200]}")
        return "".join(chunks)

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
