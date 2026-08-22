"""
Finni Signal Generator — Blends sentiment + technical scores into buy/sell signals
and produces a comparative ranking across all tracked stocks.

Blended signal = SENTIMENT_WEIGHT × sentiment_score + TECHNICAL_WEIGHT × technical_score
(default: 0.55 sentiment + 0.45 technical)

Signal thresholds produce 7-level labels from STRONG_SELL to STRONG_BUY,
each with full transparency on contributing factors.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from src.aggregator import DailyDigest
from src.config import (
    COMPANIES,
    SENTIMENT_WEIGHT,
    SIGNAL_THRESHOLDS,
    TECHNICAL_WEIGHT,
    TICKER_TO_COMPANY,
)
from src.technicals import TechnicalSnapshot

logger = logging.getLogger(__name__)


@dataclass
class StockSignal:
    """Complete daily signal for a single stock."""
    ticker: str
    company_name: str
    sector: str
    sub_sector: str

    # Scores
    sentiment_score: float
    technical_score: float
    blended_score: float

    # Labels
    sentiment_label: str
    technical_bias: str
    signal_label: str               # e.g., "STRONG_BUY"
    signal_emoji: str               # e.g., "🟢 STRONG BUY"

    # Reasoning (full transparency)
    signal_reasoning: str

    # Key data points for display
    article_count: int
    top_event: str
    top_event_title: str
    rsi: float
    sma_alignment: str
    macd_crossover: str
    last_close: float
    day_change_pct: float
    volume_notable: bool

    # Sector spillovers
    sector_spillovers: list[str] = field(default_factory=list)
    event_types: dict[str, int] = field(default_factory=dict)


@dataclass
class ComparativeAnalysis:
    """Cross-stock comparative analysis for the day."""
    date: date
    rankings: list[StockSignal]         # Sorted best to worst by blended_score
    sector_insights: list[str]          # Cross-cutting observations
    top_pick: StockSignal | None
    avoid: StockSignal | None


class SignalGenerator:
    """Generates blended signals and comparative analysis."""

    def generate(
        self,
        digests: dict[str, DailyDigest],
        snapshots: dict[str, TechnicalSnapshot],
    ) -> ComparativeAnalysis:
        """
        Generate signals for all companies and rank them.

        Args:
            digests: {ticker: DailyDigest} from aggregator
            snapshots: {ticker: TechnicalSnapshot} from technicals

        Returns:
            ComparativeAnalysis with ranked signals and sector insights
        """
        signals: list[StockSignal] = []

        for company in COMPANIES:
            ticker = company.ticker
            digest = digests.get(ticker)
            snapshot = snapshots.get(ticker)

            if digest is None or snapshot is None:
                logger.warning(f"Missing data for {ticker}, skipping signal generation")
                continue

            signal = self._generate_signal(company, digest, snapshot)
            signals.append(signal)

        # Sort by blended score (highest = best)
        signals.sort(key=lambda s: s.blended_score, reverse=True)

        # Generate sector insights
        sector_insights = self._generate_sector_insights(signals, digests)

        return ComparativeAnalysis(
            date=date.today(),
            rankings=signals,
            sector_insights=sector_insights,
            top_pick=signals[0] if signals else None,
            avoid=signals[-1] if signals else None,
        )

    def _generate_signal(
        self,
        company,
        digest: DailyDigest,
        snapshot: TechnicalSnapshot,
    ) -> StockSignal:
        """Generate a blended signal for a single stock."""
        sentiment_score = digest.composite_score
        technical_score = snapshot.technical_score

        # Blended score
        blended = SENTIMENT_WEIGHT * sentiment_score + TECHNICAL_WEIGHT * technical_score
        blended = max(-1.0, min(1.0, blended))

        # Map to signal label
        signal_label, signal_emoji = self._score_to_signal(blended)

        # Build transparent reasoning
        reasoning = self._build_reasoning(
            company, digest, snapshot, sentiment_score, technical_score, blended, signal_emoji
        )

        return StockSignal(
            ticker=company.ticker,
            company_name=company.name,
            sector=company.sector,
            sub_sector=company.sub_sector,
            sentiment_score=round(sentiment_score, 4),
            technical_score=round(technical_score, 4),
            blended_score=round(blended, 4),
            sentiment_label=digest.composite_label,
            technical_bias=snapshot.technical_bias,
            signal_label=signal_label,
            signal_emoji=signal_emoji,
            signal_reasoning=reasoning,
            article_count=digest.article_count,
            top_event=digest.top_event,
            top_event_title=digest.top_event_title,
            rsi=snapshot.rsi_14,
            sma_alignment=snapshot.sma_alignment,
            macd_crossover=snapshot.macd_crossover,
            last_close=snapshot.last_close,
            day_change_pct=snapshot.day_change_pct,
            volume_notable=snapshot.volume_notable,
            sector_spillovers=digest.sector_spillovers,
            event_types=digest.event_types,
        )

    def _score_to_signal(self, blended_score: float) -> tuple[str, str]:
        """Convert blended score to signal label and emoji."""
        for threshold, label, emoji in SIGNAL_THRESHOLDS:
            if blended_score >= threshold:
                return label, emoji
        # Should not reach here, but fallback
        return "STRONG_SELL", "🔴 STRONG SELL"

    def _build_reasoning(
        self,
        company,
        digest: DailyDigest,
        snapshot: TechnicalSnapshot,
        sentiment_score: float,
        technical_score: float,
        blended: float,
        signal_emoji: str,
    ) -> str:
        """Build a human-readable signal reasoning string."""
        parts = [f"{signal_emoji}: "]

        # Sentiment reasoning
        sent_dir = "positive" if sentiment_score > 0.05 else "negative" if sentiment_score < -0.05 else "neutral"
        parts.append(
            f"Sentiment {sentiment_score:+.2f} ({sent_dir} — "
            f"{digest.article_count} articles analyzed"
        )
        if digest.top_event:
            # Truncate top event for display
            event_preview = digest.top_event[:120] + ("..." if len(digest.top_event) > 120 else "")
            parts.append(f", top driver: {event_preview}")
        parts.append(")")

        # Technical reasoning
        tech_dir = "bullish" if technical_score > 0.1 else "bearish" if technical_score < -0.1 else "neutral"
        tech_details = []
        tech_details.append(f"RSI {snapshot.rsi_14:.0f}")
        tech_details.append(f"SMAs: {snapshot.sma_alignment.lower().replace('_', ' ')}")
        if snapshot.macd_crossover != "NEUTRAL":
            tech_details.append(f"MACD: {snapshot.macd_crossover.lower().replace('_', ' ')}")
        if snapshot.volume_notable:
            tech_details.append(f"volume {snapshot.volume_ratio:.1f}× avg")

        parts.append(
            f" + Technicals {technical_score:+.2f} ({tech_dir} — {', '.join(tech_details)})"
        )

        # Composite
        parts.append(f". Composite: {blended:+.2f}.")

        return "".join(parts)

    def _generate_sector_insights(
        self,
        signals: list[StockSignal],
        digests: dict[str, DailyDigest],
    ) -> list[str]:
        """Generate cross-cutting sector insights from signals and spillovers."""
        insights = []

        # Group signals by sector
        sector_signals: dict[str, list[StockSignal]] = {}
        for sig in signals:
            sector_signals.setdefault(sig.sector, []).append(sig)

        # Per-sector summary
        for sector, sigs in sector_signals.items():
            avg_score = sum(s.blended_score for s in sigs) / len(sigs)
            if abs(avg_score) > 0.1:
                direction = "positive" if avg_score > 0 else "negative"
                tickers = ", ".join(s.ticker.replace(".NS", "") for s in sigs)
                insights.append(
                    f"{sector}: Overall {direction} sentiment "
                    f"(avg blended: {avg_score:+.2f}) — [{tickers}]"
                )

        # Collect all sector spillovers
        all_spillovers = []
        for digest in digests.values():
            all_spillovers.extend(digest.sector_spillovers)

        # Deduplicate and add
        seen_spillovers = set()
        for spillover in all_spillovers:
            if spillover and spillover not in seen_spillovers:
                seen_spillovers.add(spillover)
                insights.append(f"Spillover: {spillover}")

        # Cross-stock observations
        if len(signals) >= 2:
            best = signals[0]
            worst = signals[-1]
            spread = best.blended_score - worst.blended_score
            if spread > 0.4:
                insights.append(
                    f"Wide dispersion today: {best.ticker.replace('.NS', '')} "
                    f"({best.blended_score:+.2f}) vs {worst.ticker.replace('.NS', '')} "
                    f"({worst.blended_score:+.2f}) — spread of {spread:.2f}"
                )

        return insights
