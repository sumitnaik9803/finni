import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.config import REPORTS_DIR, TICKER_TO_COMPANY
from src.llm_scorer import LLMScorer

logger = logging.getLogger(__name__)

@dataclass
class SectorPattern:
    sector: str
    trend: str
    pattern: str
    conviction_signal: str


PATTERN_PROMPT_TEMPLATE = """You are an expert Indian stock market strategist. 
Analyze this 14-day rolling timeline of news sentiment and signals for the {sector} sector.

TIMELINE DATA (Last 14 Days):
{timeline_data}

Based on this historical data, identify the overarching narrative.
Respond ONLY with valid JSON format:
{{"trend": "<Bearish/Neutral/Bullish/Mixed>", "pattern": "<2-3 sentences explaining the core pattern over the last 14 days>", "conviction_signal": "<STRONG BUY|BUY|HOLD|SELL|STRONG SELL>"}}
"""

class PatternAnalyzer:
    """Reads 14 days of history to find overarching sector patterns."""

    def __init__(self):
        self.scorer = LLMScorer()  # Reuse the LLM setup from llm_scorer

    async def analyze_patterns(self) -> dict[str, SectorPattern]:
        """Analyzes 14 days of history per sector and returns patterns."""
        logger.info("🔍 Loading 14-day history for pattern analysis...")
        
        # 1. Load history
        history = self._load_14_day_history()
        if not history:
            logger.info("No historical data found. Pattern analysis will be empty today.")
            return {}

        # 2. Group by sector
        sector_timelines = self._build_sector_timelines(history)
        
        # 3. Analyze each sector
        patterns = {}
        for sector, timeline_data in sector_timelines.items():
            if not timeline_data.strip():
                continue
                
            logger.info(f"   Analyzing 14-day pattern for {sector}...")
            prompt = PATTERN_PROMPT_TEMPLATE.format(sector=sector, timeline_data=timeline_data[:3000])
            
            try:
                # Try Groq first, then Gemini
                if self.scorer._groq_available:
                    await self.scorer.groq_limiter.acquire()
                    response_text = await self.scorer._call_groq(prompt)
                    parsed = self.scorer._parse_response(response_text)
                else:
                    await self.scorer.gemini_limiter.acquire()
                    response_text = await self.scorer._call_gemini(prompt)
                    parsed = self.scorer._parse_response(response_text)
                    
                patterns[sector] = SectorPattern(
                    sector=sector,
                    trend=parsed.get("trend", "Neutral"),
                    pattern=parsed.get("pattern", "Not enough data to establish a strong pattern."),
                    conviction_signal=parsed.get("conviction_signal", "HOLD")
                )
            except Exception as e:
                logger.error(f"Pattern analysis failed for {sector}: {e}")
                patterns[sector] = SectorPattern(sector, "Unknown", "Failed to analyze.", "HOLD")
                
        return patterns

    def _load_14_day_history(self) -> list[dict]:
        """Loads the raw JSON payloads of the last 14 reports."""
        if not os.path.exists(REPORTS_DIR):
            return []
            
        now = datetime.now(timezone.utc)
        history = []
        
        # Look back 14 days
        for i in range(14):
            target_date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            filepath = os.path.join(REPORTS_DIR, f"{target_date}_data.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        history.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load {filepath}: {e}")
                    
        return history

    def _build_sector_timelines(self, history: list[dict]) -> dict[str, str]:
        """Converts loaded history into string timelines grouped by sector."""
        # { sector_name: { date: [ "TCS: +0.2", ... ] } }
        sector_map = defaultdict(lambda: defaultdict(list))
        
        for daily_data in history:
            date_str = daily_data.get("date", "Unknown Date")
            sheets_data = daily_data.get("sheets_data", [])
            
            for row in sheets_data:
                ticker = row.get("Ticker")
                if not ticker:
                    continue
                    
                company = TICKER_TO_COMPANY.get(ticker)
                if not company:
                    continue
                    
                sector = company.sector
                signal = row.get("Signal", "N/A")
                blended = row.get("Blended_Score", "0.0")
                driver = row.get("Top_Event", "")
                
                if driver and driver != "None":
                    entry = f"{company.short_name}: {signal} (Score: {blended}) - {driver}"
                    sector_map[sector][date_str].append(entry)
                    
        # Format as string
        formatted_timelines = {}
        for sector, dates in sector_map.items():
            lines = []
            # Sort dates oldest to newest for the timeline
            for d in sorted(dates.keys()):
                lines.append(f"[{d}]")
                for item in dates[d]:
                    lines.append(f"  - {item}")
            formatted_timelines[sector] = "\n".join(lines)
            
        return formatted_timelines
