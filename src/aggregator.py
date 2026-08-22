"""
Finni Aggregator — Rolls up multiple article sentiment scores into a single
daily digest per company using weighted aggregation.

Weighting factors:
- Recency: exponential decay (half-life = 6 hours)
- Source reliability: tier-based (ET/BS/Mint = 1.0, Google News = 0.8)
- Impact magnitude: from LLM (HIGH = 1.5, MEDIUM = 1.0, LOW = 0.5)
- Confidence: from LLM's own confidence score
"""

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from src.config import (
    IMPACT_WEIGHTS,
    RECENCY_HALF_LIFE_HOURS,
    SOURCE_TIER_WEIGHTS,
)
from src.llm_scorer import SentimentResult

logger = logging.getLogger(__name__)


@dataclass
class DailyDigest:
    """Aggregated daily sentiment digest for a single company."""
    ticker: str
    date: date
    composite_score: float              # Weighted average, -1.0 to +1.0
    composite_label: str                # Derived from score thresholds
    article_count: int                  # Total articles analyzed
    scored_article_count: int           # Articles with non-fallback scores
    top_event: str                      # Most impactful article's reasoning
    top_event_title: str                # Title of the most impactful article
    event_types: dict[str, int] = field(default_factory=dict)
    sector_spillovers: list[str] = field(default_factory=list)
    sentiment_articles: list[dict] = field(default_factory=list)  # summary per article for report


class Aggregator:
    """Aggregates per-article sentiment results into a daily company digest."""

    def aggregate(
        self,
        ticker: str,
        scored_articles: list[SentimentResult],
        reference_time: datetime | None = None,
    ) -> DailyDigest:
        """
        Aggregate scored articles into a single DailyDigest.

        Args:
            ticker: Company ticker
            scored_articles: List of SentimentResult from LLM scoring
            reference_time: Time to compute recency from (default: now UTC)
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        today = date.today()

        if not scored_articles:
            return DailyDigest(
                ticker=ticker,
                date=today,
                composite_score=0.0,
                composite_label="NEUTRAL",
                article_count=0,
                scored_article_count=0,
                top_event="No news articles found for this company today.",
                top_event_title="(none)",
            )

        # Calculate weighted scores
        weighted_scores = []
        total_weight = 0.0
        max_impact_article = None
        max_impact_weight = 0.0

        for article in scored_articles:
            weight = self._compute_weight(article, reference_time)
            weighted_scores.append((article.sentiment_score * weight, weight))
            total_weight += weight

            # Track the most impactful article
            article_impact = weight * abs(article.sentiment_score)
            if article_impact > max_impact_weight:
                max_impact_weight = article_impact
                max_impact_article = article

        # Compute weighted average
        if total_weight > 0:
            composite_score = sum(ws for ws, _ in weighted_scores) / total_weight
        else:
            composite_score = 0.0

        # Clamp to [-1.0, +1.0]
        composite_score = max(-1.0, min(1.0, composite_score))

        # Derive label from score
        composite_label = self._score_to_label(composite_score)

        # Count event types
        event_types = Counter(a.event_type for a in scored_articles)

        # Collect sector spillovers
        spillovers = [
            a.sector_spillover
            for a in scored_articles
            if a.sector_spillover
        ]

        # Build per-article summaries for the report
        sentiment_articles = []
        for article in sorted(scored_articles, key=lambda a: abs(a.sentiment_score), reverse=True):
            sentiment_articles.append({
                "title": article.article_title,
                "source": article.article_source,
                "score": article.sentiment_score,
                "label": article.sentiment_label,
                "reasoning": article.reasoning,
                "impact": article.impact_magnitude,
                "event_type": article.event_type,
                "url": article.article_url,
            })

        # Count articles with real (non-fallback) scores
        scored_count = sum(1 for a in scored_articles if a.provider_used != "fallback")

        return DailyDigest(
            ticker=ticker,
            date=today,
            composite_score=round(composite_score, 4),
            composite_label=composite_label,
            article_count=len(scored_articles),
            scored_article_count=scored_count,
            top_event=max_impact_article.reasoning if max_impact_article else "",
            top_event_title=max_impact_article.article_title if max_impact_article else "",
            event_types=dict(event_types),
            sector_spillovers=spillovers,
            sentiment_articles=sentiment_articles,
        )

    def _compute_weight(
        self,
        article: SentimentResult,
        reference_time: datetime,
    ) -> float:
        """
        Compute the aggregation weight for a single article.

        weight = recency_w × source_w × impact_w × confidence
        """
        # Recency weight (exponential decay)
        hours_ago = (reference_time - article.article_published_at).total_seconds() / 3600.0
        hours_ago = max(0, hours_ago)
        recency_w = math.exp(-0.693 * hours_ago / RECENCY_HALF_LIFE_HOURS)
        # 0.693 ≈ ln(2), so weight halves every RECENCY_HALF_LIFE_HOURS

        # Source tier weight
        source_tier = self._infer_source_tier(article.article_source)
        source_w = SOURCE_TIER_WEIGHTS.get(source_tier, 0.6)

        # Impact magnitude weight
        impact_w = IMPACT_WEIGHTS.get(article.impact_magnitude, 1.0)

        # LLM confidence
        confidence = max(0.1, article.confidence)

        weight = recency_w * source_w * impact_w * confidence
        return weight

    def _infer_source_tier(self, source_name: str) -> int:
        """Infer source tier from the source name string."""
        name_lower = source_name.lower()
        if any(kw in name_lower for kw in ["economic times", "business standard", "livemint", "mint"]):
            return 1
        elif "google news" in name_lower:
            return 2
        else:
            return 3

    @staticmethod
    def _score_to_label(score: float) -> str:
        """Convert a sentiment score to a human-readable label."""
        if score >= 0.5:
            return "VERY_BULLISH"
        elif score >= 0.2:
            return "BULLISH"
        elif score >= 0.05:
            return "LEAN_BULLISH"
        elif score >= -0.05:
            return "NEUTRAL"
        elif score >= -0.2:
            return "LEAN_BEARISH"
        elif score >= -0.5:
            return "BEARISH"
        else:
            return "VERY_BEARISH"
