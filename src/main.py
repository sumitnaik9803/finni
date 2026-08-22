"""
Finni Pipeline Orchestrator — Runs the full daily analysis pipeline.

Sequence:
1. Load company configuration
2. Fetch news from RSS feeds (async)
3. Score each article via LLM (Groq primary, Gemini fallback)
4. Aggregate per-company daily sentiment digest
5. Fetch price data and compute technical indicators
6. Generate blended buy/sell signals
7. Build Markdown report + structured data
8. Publish to Google Sheets
9. Save Markdown report to data/reports/

Designed to run as a GitHub Actions cron job at ~6:45 AM IST (1:15 AM UTC),
completing well before the 9:00 AM market open.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import date

from src.aggregator import Aggregator
from src.config import COMPANIES, get_company
from src.llm_scorer import LLMScorer
from src.news_fetcher import NewsFetcher
from src.report_builder import ReportBuilder
from src.sheets_publisher import SheetsPublisher
from src.signal_generator import SignalGenerator
from src.technicals import TechnicalAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("finni")


async def run_pipeline():
    """Execute the full Finni pipeline."""
    start_time = time.time()
    logger.info("🚀 Finni pipeline starting")
    logger.info(f"📅 Date: {date.today().isoformat()}")
    logger.info(f"📋 Tracking {len(COMPANIES)} companies")

    # ──────────────────────────────────────────
    # Step 1: Load configuration
    # ──────────────────────────────────────────
    companies = COMPANIES
    ticker_list = [c.ticker for c in companies]
    logger.info(f"🏢 Companies: {', '.join(c.short_name for c in companies)}")

    # ──────────────────────────────────────────
    # Step 2: Fetch news
    # ──────────────────────────────────────────
    logger.info("📰 Step 2/8: Fetching news from RSS feeds...")
    fetcher = NewsFetcher()
    news_map = await fetcher.fetch_all(companies)
    total_articles = sum(len(v) for v in news_map.values())
    logger.info(f"📰 Fetched {total_articles} articles across {len(news_map)} companies")

    # Log per-company breakdown
    for ticker in ticker_list:
        articles = news_map.get(ticker, [])
        logger.info(f"   {ticker}: {len(articles)} articles")

    # ──────────────────────────────────────────
    # Step 3: Score articles via LLM
    # ──────────────────────────────────────────
    logger.info("🤖 Step 3/8: Scoring articles via LLM...")
    scorer = LLMScorer()
    scored_map = {}

    for ticker in ticker_list:
        articles = news_map.get(ticker, [])
        if not articles:
            scored_map[ticker] = []
            logger.info(f"   {ticker}: No articles to score")
            continue

        company = get_company(ticker)
        scored_map[ticker] = await scorer.score_batch(articles, company)
        logger.info(f"   {ticker}: Scored {len(scored_map[ticker])} articles")

    logger.info("🤖 Sentiment scoring complete")

    # ──────────────────────────────────────────
    # Step 4: Aggregate daily digests
    # ──────────────────────────────────────────
    logger.info("📊 Step 4/8: Aggregating daily digests...")
    aggregator = Aggregator()
    digests = {}

    for ticker in ticker_list:
        scored = scored_map.get(ticker, [])
        digests[ticker] = aggregator.aggregate(ticker, scored)
        d = digests[ticker]
        logger.info(
            f"   {ticker}: composite={d.composite_score:+.3f} "
            f"({d.composite_label}), {d.article_count} articles"
        )

    # ──────────────────────────────────────────
    # Step 5: Technical analysis
    # ──────────────────────────────────────────
    logger.info("📈 Step 5/8: Computing technical indicators...")
    tech_analyzer = TechnicalAnalyzer()
    snapshots = {}

    for ticker in ticker_list:
        snapshots[ticker] = tech_analyzer.analyze(ticker)
        s = snapshots[ticker]
        logger.info(
            f"   {ticker}: close=₹{s.last_close:,.2f}, "
            f"RSI={s.rsi_14:.0f}, SMAs={s.sma_alignment}, "
            f"score={s.technical_score:+.3f} ({s.technical_bias})"
        )

    # ──────────────────────────────────────────
    # Step 6: Generate signals
    # ──────────────────────────────────────────
    logger.info("🎯 Step 6/8: Generating signals...")
    signal_gen = SignalGenerator()
    analysis = signal_gen.generate(digests, snapshots)

    logger.info("🏆 Rankings:")
    for i, sig in enumerate(analysis.rankings, 1):
        short = sig.ticker.replace(".NS", "")
        logger.info(
            f"   #{i} {short}: {sig.signal_emoji} "
            f"(blended={sig.blended_score:+.3f}, "
            f"sent={sig.sentiment_score:+.3f}, "
            f"tech={sig.technical_score:+.3f})"
        )

    # ──────────────────────────────────────────
    # Step 7: Build report
    # ──────────────────────────────────────────
    logger.info("📝 Step 7/8: Building report...")
    builder = ReportBuilder()
    report = builder.build(analysis, digests, snapshots, pipeline_start_time=start_time)

    # Save Markdown report to disk
    builder.save_markdown(report)
    logger.info(f"📝 Markdown report saved for {report['date']}")

    # ──────────────────────────────────────────
    # Step 8: Publish to Google Sheets
    # ──────────────────────────────────────────
    logger.info("📊 Step 8/8: Publishing to Google Sheets...")
    try:
        publisher = SheetsPublisher()
        publisher.publish_daily(report)
        logger.info("📊 Google Sheets updated successfully")
    except Exception as e:
        logger.error(f"Google Sheets publishing failed: {e}")
        logger.info("Pipeline will continue — Markdown report is already saved.")

    # ──────────────────────────────────────────
    # Complete
    # ──────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info(f"✅ Finni pipeline complete in {elapsed / 60:.1f} minutes")
    logger.info(f"📊 Report available at: data/reports/{report['date']}.md")

    return report


def main():
    """Entry point for the pipeline."""
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Pipeline failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
