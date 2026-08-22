"""
Finni Report Builder — Generates Markdown daily reports and structured data
for Google Sheets publishing.

Produces:
1. A formatted Markdown report saved to data/reports/YYYY-MM-DD.md
2. A structured dict ready for the SheetsPublisher
"""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

from src.aggregator import DailyDigest
from src.config import REPORTS_DIR, TICKER_TO_COMPANY
from src.pattern_analyzer import SectorPattern
from src.signal_generator import ComparativeAnalysis, StockSignal
from src.technicals import TechnicalSnapshot

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


class ReportBuilder:
    """Builds daily reports in Markdown and structured formats."""

    def build(
        self,
        analysis: ComparativeAnalysis,
        digests: dict[str, DailyDigest],
        snapshots: dict[str, TechnicalSnapshot],
        patterns: dict[str, SectorPattern],
        pipeline_start_time: float | None = None,
    ) -> dict:
        """
        Build the complete daily report.

        Returns:
            dict with keys:
            - "markdown": str (full Markdown report)
            - "sheets_data": list[dict] (rows for Google Sheets)
            - "dashboard_data": dict (latest snapshot for dashboard sheet)
            - "date": str (ISO date)
        """
        now_ist = datetime.now(IST)
        report_date = now_ist.strftime("%Y-%m-%d")
        timestamp = now_ist.strftime("%Y-%m-%d %H:%M IST")

        # Pipeline runtime
        if pipeline_start_time:
            import time
            elapsed = time.time() - pipeline_start_time
            runtime_str = f"{elapsed / 60:.1f} minutes"
        else:
            runtime_str = "N/A"

        # Build Markdown
        md = self._build_markdown(analysis, digests, snapshots, patterns, report_date, timestamp, runtime_str)

        # Build Sheets data
        sheets_rows = self._build_sheets_rows(analysis, digests, snapshots, report_date)
        dashboard = self._build_dashboard_data(analysis, digests, snapshots, report_date, timestamp, runtime_str)

        return {
            "markdown": md,
            "sheets_data": sheets_rows,
            "dashboard_data": dashboard,
            "date": report_date,
        }

    def save_reports(self, report: dict):
        """Save the Markdown report and JSON data to the data/reports/ directory."""
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        # Save Markdown
        md_filepath = os.path.join(REPORTS_DIR, f"{report['date']}.md")
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(report["markdown"])
            
        # Save JSON (for historical pattern analysis)
        json_filepath = os.path.join(REPORTS_DIR, f"{report['date']}_data.json")
        with open(json_filepath, "w", encoding="utf-8") as f:
            data_to_save = {k: v for k, v in report.items() if k != "markdown"}
            json.dump(data_to_save, f, indent=2)
            
        logger.info(f"Reports (MD/JSON) saved for {report['date']}")

    def _build_markdown(
        self,
        analysis: ComparativeAnalysis,
        digests: dict[str, DailyDigest],
        snapshots: dict[str, TechnicalSnapshot],
        patterns: dict[str, SectorPattern],
        report_date: str,
        timestamp: str,
        runtime_str: str,
    ) -> str:
        """Build the full Markdown report string."""
        lines = []

        # Header
        lines.append(f"# 📊 Finni Daily Report — {report_date}")
        lines.append("")
        lines.append("> ⚠️ **Disclaimer**: This is an automated analysis tool, NOT financial advice.")
        lines.append("> Signals are rule-based heuristics from public news sentiment and basic technical indicators.")
        lines.append(f"> Generated at {timestamp} | Pipeline runtime: {runtime_str}")
        lines.append("")

        # ── Sector Patterns (14-Day) ──
        if patterns:
            lines.append("## 📈 14-Day Sector Patterns")
            lines.append("")
            for sector, pattern in patterns.items():
                lines.append(f"### {sector}")
                lines.append(f"- **Trend**: {pattern.trend}")
                lines.append(f"- **Conviction Signal**: {pattern.conviction_signal}")
                lines.append(f"- **Narrative**: {pattern.pattern}")
                lines.append("")

        # ── Ranking Table ──
        lines.append("## 🏆 Today's Ranking")
        lines.append("")
        lines.append("| Rank | Stock | Signal | Blended | Sentiment | Technical | Last Close | Day Chg | Key Driver |")
        lines.append("|------|-------|--------|---------|-----------|-----------|------------|---------|------------|")

        for i, signal in enumerate(analysis.rankings, 1):
            short = signal.ticker.replace(".NS", "")
            # Truncate top event for table
            event_short = signal.top_event[:50] + ("..." if len(signal.top_event) > 50 else "") if signal.top_event else "—"
            lines.append(
                f"| {i} | **{short}** | {signal.signal_emoji} | "
                f"{signal.blended_score:+.2f} | {signal.sentiment_score:+.2f} | "
                f"{signal.technical_score:+.2f} | ₹{signal.last_close:,.2f} | "
                f"{signal.day_change_pct:+.1f}% | {event_short} |"
            )

        lines.append("")

        # ── Per-Stock Analysis ──
        lines.append("## 📰 Per-Stock Analysis")
        lines.append("")

        for signal in analysis.rankings:
            short = signal.ticker.replace(".NS", "")
            digest = digests.get(signal.ticker)
            snapshot = snapshots.get(signal.ticker)

            lines.append(f"### {short} — {signal.signal_emoji}")
            lines.append("")

            # Sentiment section
            lines.append(f"**Sentiment**: {signal.sentiment_score:+.2f} ({signal.sentiment_label}) — {signal.article_count} articles analyzed")
            if digest and digest.sentiment_articles:
                for art in digest.sentiment_articles[:3]:  # Top 3 articles
                    score_str = f"{art['score']:+.2f}"
                    lines.append(f"- [{art['title'][:80]}]({art['url']}) ({art['source']}, {score_str}, {art['impact']})")
            lines.append("")

            # Spillovers
            if signal.sector_spillovers:
                for sp in signal.sector_spillovers[:2]:
                    lines.append(f"- 🔄 *Spillover*: {sp}")
                lines.append("")

            # Technicals section
            if snapshot:
                lines.append(
                    f"**Technicals**: {signal.technical_score:+.2f} ({signal.technical_bias}) — "
                    f"RSI: {snapshot.rsi_14:.0f}, "
                    f"SMAs: {snapshot.sma_alignment.lower().replace('_', ' ')}, "
                    f"MACD: {snapshot.macd_crossover.lower().replace('_', ' ')}"
                )
                if snapshot.volume_notable:
                    lines.append(f"- ⚡ Unusual volume: {snapshot.volume_ratio:.1f}× 20-day average")
                lines.append("")

            # Full signal reasoning
            lines.append(f"**Signal reasoning**: {signal.signal_reasoning}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ── Comparative Matrix ──
        lines.append("## 🔄 Comparative Matrix")
        lines.append("")
        lines.append("| Stock | Sentiment | Technical | Blended | RSI | SMA Align | MACD | Volume |")
        lines.append("|-------|-----------|-----------|---------|-----|-----------|------|--------|")

        for signal in analysis.rankings:
            short = signal.ticker.replace(".NS", "")
            snapshot = snapshots.get(signal.ticker)
            vol_flag = "⚡" if signal.volume_notable else "—"
            lines.append(
                f"| {short} | {signal.sentiment_score:+.2f} | {signal.technical_score:+.2f} | "
                f"{signal.blended_score:+.2f} | {signal.rsi:.0f} | {signal.sma_alignment} | "
                f"{signal.macd_crossover.split('_')[0][:4]} | {vol_flag} |"
            )

        lines.append("")

        # ── Sector Themes ──
        if analysis.sector_insights:
            lines.append("## 📈 Sector Themes & Spillovers")
            lines.append("")
            for insight in analysis.sector_insights:
                lines.append(f"- {insight}")
            lines.append("")

        # ── Footer ──
        lines.append("---")
        lines.append(f"*Report generated by Finni v1.0 at {timestamp}*")

        return "\n".join(lines)

    def _build_sheets_rows(
        self,
        analysis: ComparativeAnalysis,
        digests: dict[str, DailyDigest],
        snapshots: dict[str, TechnicalSnapshot],
        report_date: str,
    ) -> list[dict]:
        """Build rows for the 'Daily Log' sheet (one row per stock per day)."""
        rows = []
        for rank, signal in enumerate(analysis.rankings, 1):
            snapshot = snapshots.get(signal.ticker)
            digest = digests.get(signal.ticker)

            rows.append({
                "Date": report_date,
                "Rank": rank,
                "Ticker": signal.ticker.replace(".NS", ""),
                "Company": signal.company_name,
                "Signal": signal.signal_emoji,
                "Blended Score": signal.blended_score,
                "Sentiment Score": signal.sentiment_score,
                "Sentiment Label": signal.sentiment_label,
                "Technical Score": signal.technical_score,
                "Technical Bias": signal.technical_bias,
                "Last Close": signal.last_close,
                "Day Change %": signal.day_change_pct,
                "RSI": signal.rsi,
                "SMA Alignment": signal.sma_alignment,
                "MACD": signal.macd_crossover,
                "Articles": signal.article_count,
                "Top Event": signal.top_event_title[:100] if signal.top_event_title else "",
                "Key Reasoning": signal.top_event[:150] if signal.top_event else "",
                "Volume Notable": "Yes" if signal.volume_notable else "No",
            })

        return rows

    def _build_dashboard_data(
        self,
        analysis: ComparativeAnalysis,
        digests: dict[str, DailyDigest],
        snapshots: dict[str, TechnicalSnapshot],
        report_date: str,
        timestamp: str,
        runtime_str: str,
    ) -> dict:
        """Build data for the 'Dashboard' sheet (overwritten daily)."""
        return {
            "header": {
                "report_date": report_date,
                "generated_at": timestamp,
                "runtime": runtime_str,
                "total_articles": sum(d.article_count for d in digests.values()),
                "stocks_analyzed": len(analysis.rankings),
            },
            "rankings": [
                {
                    "rank": i,
                    "ticker": s.ticker.replace(".NS", ""),
                    "signal": s.signal_emoji,
                    "blended": s.blended_score,
                    "sentiment": s.sentiment_score,
                    "technical": s.technical_score,
                    "last_close": s.last_close,
                    "articles": s.article_count,
                    "top_driver": s.top_event[:80] if s.top_event else "—",
                }
                for i, s in enumerate(analysis.rankings, 1)
            ],
            "sector_insights": analysis.sector_insights,
        }
