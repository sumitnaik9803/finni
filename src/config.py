"""
Finni Configuration — Company taxonomy, news sources, API config, and constants.
"""

from dataclasses import dataclass, field
import os


# ──────────────────────────────────────────────
# Company Configuration
# ──────────────────────────────────────────────

@dataclass
class CompanyConfig:
    """Configuration for a single tracked company."""
    ticker: str                     # yfinance ticker (e.g., "RELIANCE.NS")
    name: str                       # Full company name
    short_name: str                 # Short display name
    sector: str                     # NSE macro sector
    sub_sector: str                 # NSE sub-sector / basic industry
    keywords: list[str] = field(default_factory=list)   # Search keywords for news matching
    peers: list[str] = field(default_factory=list)       # Peer tickers from our watchlist


COMPANIES: list[CompanyConfig] = [
    CompanyConfig(
        ticker="RELIANCE.NS",
        name="Reliance Industries Limited",
        short_name="Reliance",
        sector="Diversified",
        sub_sector="Oil & Gas / Telecom / Retail",
        keywords=[
            "reliance", "reliance industries", "ril", "jio", "reliance jio",
            "reliance retail", "mukesh ambani", "reliance bp",
        ],
        peers=["BHARTIARTL.NS"],
    ),
    CompanyConfig(
        ticker="TCS.NS",
        name="Tata Consultancy Services Limited",
        short_name="TCS",
        sector="Information Technology",
        sub_sector="IT Consulting & Software",
        keywords=[
            "tcs", "tata consultancy", "tata consultancy services",
            "tcs share", "tcs results",
        ],
        peers=[],
    ),
    CompanyConfig(
        ticker="HDFCBANK.NS",
        name="HDFC Bank Limited",
        short_name="HDFC Bank",
        sector="Financial Services",
        sub_sector="Private Sector Banks",
        keywords=[
            "hdfc bank", "hdfcbank", "hdfc", "hdfc bank share",
            "hdfc results", "hdfc bank npa",
        ],
        peers=[],
    ),
    CompanyConfig(
        ticker="MARUTI.NS",
        name="Maruti Suzuki India Limited",
        short_name="Maruti Suzuki",
        sector="Automobile",
        sub_sector="Passenger Vehicles",
        keywords=[
            "maruti", "maruti suzuki", "maruti share", "maruti sales",
            "suzuki india", "maruti nexa", "maruti alto", "maruti brezza",
        ],
        peers=[],
    ),
    CompanyConfig(
        ticker="SUNPHARMA.NS",
        name="Sun Pharmaceutical Industries Limited",
        short_name="Sun Pharma",
        sector="Healthcare",
        sub_sector="Pharmaceuticals — Formulations",
        keywords=[
            "sun pharma", "sun pharmaceutical", "sunpharma", "sun pharma share",
            "sun pharma usfda", "sun pharma results",
        ],
        peers=[],
    ),
    CompanyConfig(
        ticker="ITC.NS",
        name="ITC Limited",
        short_name="ITC",
        sector="FMCG",
        sub_sector="Cigarettes / FMCG / Hotels",
        keywords=[
            "itc", "itc limited", "itc share", "itc results",
            "itc fmcg", "itc hotels", "itc cigarettes",
        ],
        peers=["TITAN.NS"],
    ),
    CompanyConfig(
        ticker="TITAN.NS",
        name="Titan Company Limited",
        short_name="Titan",
        sector="Consumer Discretionary",
        sub_sector="Gems, Jewellery & Watches",
        keywords=[
            "titan company", "titan share", "titan stock", "tanishq",
            "titan eye", "titan watches", "titan results",
        ],
        peers=["ITC.NS"],
    ),
    CompanyConfig(
        ticker="BHARTIARTL.NS",
        name="Bharti Airtel Limited",
        short_name="Bharti Airtel",
        sector="Telecom",
        sub_sector="Telecom Services — Mobile & Broadband",
        keywords=[
            "airtel", "bharti airtel", "airtel share", "airtel tariff",
            "airtel 5g", "airtel results", "bharti airtel share",
        ],
        peers=["RELIANCE.NS"],
    ),
]

# Build lookup helpers
TICKER_TO_COMPANY: dict[str, CompanyConfig] = {c.ticker: c for c in COMPANIES}
SHORTNAME_TO_COMPANY: dict[str, CompanyConfig] = {c.short_name.lower(): c for c in COMPANIES}


def get_company(ticker: str) -> CompanyConfig:
    """Get company config by ticker. Raises KeyError if not found."""
    return TICKER_TO_COMPANY[ticker]


def get_all_tickers() -> list[str]:
    """Return all tracked ticker symbols."""
    return [c.ticker for c in COMPANIES]


# ──────────────────────────────────────────────
# News Source Configuration
# ──────────────────────────────────────────────

@dataclass
class NewsSourceConfig:
    """Configuration for a news RSS feed source."""
    name: str
    url: str
    tier: int       # 1 = highest quality/reliability, 2 = good, 3 = aggregator
    category: str   # "general_market" or "company_specific"


NEWS_SOURCES: list[NewsSourceConfig] = [
    NewsSourceConfig(
        name="Economic Times Markets",
        url="https://economictimes.indiatimes.com/rssfeeds/1977021501.cms",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="Business Standard Markets",
        url="https://www.business-standard.com/rss/markets-106.rss",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="LiveMint Markets",
        url="https://www.livemint.com/rss/markets",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="Economic Times Business",
        url="https://economictimes.indiatimes.com/rssfeeds/1286551815.cms",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="Moneycontrol Top News",
        url="https://www.moneycontrol.com/rss/MCtopnews.xml",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="Moneycontrol Business",
        url="https://www.moneycontrol.com/rss/business.xml",
        tier=1,
        category="general_market",
    ),
    NewsSourceConfig(
        name="Economic Times IT",
        url="https://economictimes.indiatimes.com/tech/software/rssfeeds/13357555.cms",
        tier=2,
        category="general_market",
    ),
]

# Google News RSS template for company-specific searches
GOOGLE_NEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search?"
    "q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)


# ──────────────────────────────────────────────
# Pipeline Constants
# ──────────────────────────────────────────────

# News window: how many hours back to look for articles
NEWS_WINDOW_HOURS = 18

# Sentiment vs. technical weighting for the blended signal
SENTIMENT_WEIGHT = 0.55
TECHNICAL_WEIGHT = 0.45

# Signal thresholds (blended score → signal label)
SIGNAL_THRESHOLDS = [
    (0.50, "STRONG_BUY",    "🟢 STRONG BUY"),
    (0.25, "BUY",           "🔵 BUY"),
    (0.10, "LEAN_BULLISH",  "⬆️ LEAN BULLISH"),
    (-0.10, "NEUTRAL",      "⚪ NEUTRAL"),
    (-0.25, "LEAN_BEARISH", "⬇️ LEAN BEARISH"),
    (-0.50, "SELL",         "🔴 SELL"),
    (-1.01, "STRONG_SELL",  "🔴 STRONG SELL"),  # -1.01 to catch -1.0
]

# Source reliability weights for aggregation
SOURCE_TIER_WEIGHTS = {
    1: 1.0,
    2: 0.8,
    3: 0.6,
}

# Impact magnitude weights for aggregation
IMPACT_WEIGHTS = {
    "HIGH": 1.5,
    "MEDIUM": 1.0,
    "LOW": 0.5,
}

# Recency decay parameters (exponential decay)
RECENCY_HALF_LIFE_HOURS = 6.0  # weight halves every 6 hours


# ──────────────────────────────────────────────
# Technical Indicator Configuration
# ──────────────────────────────────────────────

# How much historical data to fetch for indicator calculation
TECHNICAL_LOOKBACK_PERIOD = "8mo"   # 8 months to ensure SMA200 has enough data
TECHNICAL_INTERVAL = "1d"           # Daily candles

# RSI thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Volume ratio threshold for "unusual volume" flag
VOLUME_RATIO_NOTABLE = 1.5


# ──────────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────────

# Groq (primary)
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_MAX_RPM = 25                  # Stay under 30 RPM limit with headroom
GROQ_MAX_TOKENS = 500              # Max response tokens per call
GROQ_TEMPERATURE = 0.1             # Low temp for consistent structured output

# Gemini (fallback)
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_RPM = 12                # Stay under 15 RPM limit
GEMINI_MAX_TOKENS = 500
GEMINI_TEMPERATURE = 0.1


# ──────────────────────────────────────────────
# API Keys (read from environment, never hardcoded)
# ──────────────────────────────────────────────

def get_groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError("GROQ_API_KEY environment variable not set")
    return key


def get_gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY environment variable not set")
    return key


def get_google_sheets_credentials() -> str:
    creds = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    if not creds:
        raise EnvironmentError("GOOGLE_SHEETS_CREDENTIALS environment variable not set")
    return creds


def get_google_sheet_id() -> str:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise EnvironmentError("GOOGLE_SHEET_ID environment variable not set")
    return sheet_id


# ──────────────────────────────────────────────
# Output Paths
# ──────────────────────────────────────────────

REPORTS_DIR = "data/reports"
