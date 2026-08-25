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
        sector="Energy",
        sub_sector="Oil & Gas",
        keywords=["reliance", "reliance share", "reliance industries limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TCS.NS",
        name="Tata Consultancy Services Limited",
        short_name="TCS",
        sector="IT",
        sub_sector="Software",
        keywords=["tcs", "tcs share", "tata consultancy services limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HDFCBANK.NS",
        name="HDFC Bank Limited",
        short_name="HDFC Bank",
        sector="Financials",
        sub_sector="Banks",
        keywords=["hdfc bank", "hdfc bank share", "hdfc bank limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ICICIBANK.NS",
        name="ICICI Bank Limited",
        short_name="ICICI Bank",
        sector="Financials",
        sub_sector="Banks",
        keywords=["icici bank", "icici bank share", "icici bank limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="INFY.NS",
        name="Infosys Limited",
        short_name="Infosys",
        sector="IT",
        sub_sector="Software",
        keywords=["infosys", "infosys share", "infosys limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ITC.NS",
        name="ITC Limited",
        short_name="ITC",
        sector="FMCG",
        sub_sector="FMCG",
        keywords=["itc", "itc share", "itc limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="SBIN.NS",
        name="State Bank of India",
        short_name="SBI",
        sector="Financials",
        sub_sector="Banks",
        keywords=["sbi", "sbi share", "state bank of india"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BHARTIARTL.NS",
        name="Bharti Airtel Limited",
        short_name="Bharti Airtel",
        sector="Telecom",
        sub_sector="Telecom Services",
        keywords=["bharti airtel", "bharti airtel share", "bharti airtel limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HINDUNILVR.NS",
        name="Hindustan Unilever Limited",
        short_name="HUL",
        sector="FMCG",
        sub_sector="FMCG",
        keywords=["hul", "hul share", "hindustan unilever limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="LT.NS",
        name="Larsen & Toubro Limited",
        short_name="L&T",
        sector="Industrials",
        sub_sector="Construction",
        keywords=["l&t", "l&t share", "larsen & toubro limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BAJFINANCE.NS",
        name="Bajaj Finance Limited",
        short_name="Bajaj Finance",
        sector="Financials",
        sub_sector="NBFC",
        keywords=["bajaj finance", "bajaj finance share", "bajaj finance limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="AXISBANK.NS",
        name="Axis Bank Limited",
        short_name="Axis Bank",
        sector="Financials",
        sub_sector="Banks",
        keywords=["axis bank", "axis bank share", "axis bank limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="KOTAKBANK.NS",
        name="Kotak Mahindra Bank Limited",
        short_name="Kotak Bank",
        sector="Financials",
        sub_sector="Banks",
        keywords=["kotak bank", "kotak bank share", "kotak mahindra bank limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="MARUTI.NS",
        name="Maruti Suzuki India Limited",
        short_name="Maruti Suzuki",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["maruti suzuki", "maruti suzuki share", "maruti suzuki india limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="SUNPHARMA.NS",
        name="Sun Pharmaceutical Industries",
        short_name="Sun Pharma",
        sector="Healthcare",
        sub_sector="Pharmaceuticals",
        keywords=["sun pharma", "sun pharma share", "sun pharmaceutical industries"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ULTRACEMCO.NS",
        name="UltraTech Cement Limited",
        short_name="UltraTech",
        sector="Materials",
        sub_sector="Cement",
        keywords=["ultratech", "ultratech share", "ultratech cement limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TATAMOTORS.NS",
        name="Tata Motors Limited",
        short_name="Tata Motors",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["tata motors", "tata motors share", "tata motors limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="NTPC.NS",
        name="NTPC Limited",
        short_name="NTPC",
        sector="Energy",
        sub_sector="Power",
        keywords=["ntpc", "ntpc share", "ntpc limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TITAN.NS",
        name="Titan Company Limited",
        short_name="Titan",
        sector="Consumer Discretionary",
        sub_sector="Jewellery",
        keywords=["titan", "titan share", "titan company limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ONGC.NS",
        name="Oil and Natural Gas Corporation",
        short_name="ONGC",
        sector="Energy",
        sub_sector="Oil & Gas",
        keywords=["ongc", "ongc share", "oil and natural gas corporation"],
        peers=[],
    ),
    CompanyConfig(
        ticker="POWERGRID.NS",
        name="Power Grid Corporation of India",
        short_name="Power Grid",
        sector="Energy",
        sub_sector="Power",
        keywords=["power grid", "power grid share", "power grid corporation of india"],
        peers=[],
    ),
    CompanyConfig(
        ticker="COALINDIA.NS",
        name="Coal India Limited",
        short_name="Coal India",
        sector="Energy",
        sub_sector="Coal",
        keywords=["coal india", "coal india share", "coal india limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ASIANPAINT.NS",
        name="Asian Paints Limited",
        short_name="Asian Paints",
        sector="Materials",
        sub_sector="Paints",
        keywords=["asian paints", "asian paints share", "asian paints limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BAJAJFINSV.NS",
        name="Bajaj Finserv Limited",
        short_name="Bajaj Finserv",
        sector="Financials",
        sub_sector="Holding",
        keywords=["bajaj finserv", "bajaj finserv share", "bajaj finserv limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ADANIENT.NS",
        name="Adani Enterprises Limited",
        short_name="Adani Ent",
        sector="Industrials",
        sub_sector="Conglomerate",
        keywords=["adani ent", "adani ent share", "adani enterprises limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="ADANIPORTS.NS",
        name="Adani Ports and SEZ Limited",
        short_name="Adani Ports",
        sector="Industrials",
        sub_sector="Infrastructure",
        keywords=["adani ports", "adani ports share", "adani ports and sez limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="M&M.NS",
        name="Mahindra & Mahindra Limited",
        short_name="M&M",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["m&m", "m&m share", "mahindra & mahindra limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="WIPRO.NS",
        name="Wipro Limited",
        short_name="Wipro",
        sector="IT",
        sub_sector="Software",
        keywords=["wipro", "wipro share", "wipro limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HCLTECH.NS",
        name="HCL Technologies Limited",
        short_name="HCLTech",
        sector="IT",
        sub_sector="Software",
        keywords=["hcltech", "hcltech share", "hcl technologies limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TATASTEEL.NS",
        name="Tata Steel Limited",
        short_name="Tata Steel",
        sector="Materials",
        sub_sector="Steel",
        keywords=["tata steel", "tata steel share", "tata steel limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="JSWSTEEL.NS",
        name="JSW Steel Limited",
        short_name="JSW Steel",
        sector="Materials",
        sub_sector="Steel",
        keywords=["jsw steel", "jsw steel share", "jsw steel limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HINDALCO.NS",
        name="Hindalco Industries Limited",
        short_name="Hindalco",
        sector="Materials",
        sub_sector="Metals",
        keywords=["hindalco", "hindalco share", "hindalco industries limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="GRASIM.NS",
        name="Grasim Industries Limited",
        short_name="Grasim",
        sector="Materials",
        sub_sector="Cement/Chemicals",
        keywords=["grasim", "grasim share", "grasim industries limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TECHM.NS",
        name="Tech Mahindra Limited",
        short_name="Tech Mahindra",
        sector="IT",
        sub_sector="Software",
        keywords=["tech mahindra", "tech mahindra share", "tech mahindra limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="LTIM.NS",
        name="LTIMindtree Limited",
        short_name="LTIMindtree",
        sector="IT",
        sub_sector="Software",
        keywords=["ltimindtree", "ltimindtree share", "ltimindtree limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="INDUSINDBK.NS",
        name="IndusInd Bank Limited",
        short_name="IndusInd Bank",
        sector="Financials",
        sub_sector="Banks",
        keywords=["indusind bank", "indusind bank share", "indusind bank limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BAJAJ-AUTO.NS",
        name="Bajaj Auto Limited",
        short_name="Bajaj Auto",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["bajaj auto", "bajaj auto share", "bajaj auto limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="EICHERMOT.NS",
        name="Eicher Motors Limited",
        short_name="Eicher Motors",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["eicher motors", "eicher motors share", "eicher motors limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HEROMOTOCO.NS",
        name="Hero MotoCorp Limited",
        short_name="Hero MotoCorp",
        sector="Auto",
        sub_sector="Automobiles",
        keywords=["hero motocorp", "hero motocorp share", "hero motocorp limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="DRREDDY.NS",
        name="Dr. Reddy's Laboratories",
        short_name="Dr. Reddy's",
        sector="Healthcare",
        sub_sector="Pharmaceuticals",
        keywords=["dr. reddy's", "dr. reddy's share", "dr. reddy's laboratories"],
        peers=[],
    ),
    CompanyConfig(
        ticker="CIPLA.NS",
        name="Cipla Limited",
        short_name="Cipla",
        sector="Healthcare",
        sub_sector="Pharmaceuticals",
        keywords=["cipla", "cipla share", "cipla limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="DIVISLAB.NS",
        name="Divi's Laboratories Limited",
        short_name="Divi's Lab",
        sector="Healthcare",
        sub_sector="Pharmaceuticals",
        keywords=["divi's lab", "divi's lab share", "divi's laboratories limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="APOLLOHOSP.NS",
        name="Apollo Hospitals Enterprise",
        short_name="Apollo Hospitals",
        sector="Healthcare",
        sub_sector="Hospitals",
        keywords=["apollo hospitals", "apollo hospitals share", "apollo hospitals enterprise"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BRITANNIA.NS",
        name="Britannia Industries Limited",
        short_name="Britannia",
        sector="FMCG",
        sub_sector="FMCG",
        keywords=["britannia", "britannia share", "britannia industries limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="NESTLEIND.NS",
        name="Nestle India Limited",
        short_name="Nestle India",
        sector="FMCG",
        sub_sector="FMCG",
        keywords=["nestle india", "nestle india share", "nestle india limited"],
        peers=[],
    ),
    CompanyConfig(
        ticker="TATACONSUM.NS",
        name="Tata Consumer Products",
        short_name="Tata Consumer",
        sector="FMCG",
        sub_sector="FMCG",
        keywords=["tata consumer", "tata consumer share", "tata consumer products"],
        peers=[],
    ),
    CompanyConfig(
        ticker="HDFCLIFE.NS",
        name="HDFC Life Insurance",
        short_name="HDFC Life",
        sector="Financials",
        sub_sector="Insurance",
        keywords=["hdfc life", "hdfc life share", "hdfc life insurance"],
        peers=[],
    ),
    CompanyConfig(
        ticker="SBILIFE.NS",
        name="SBI Life Insurance",
        short_name="SBI Life",
        sector="Financials",
        sub_sector="Insurance",
        keywords=["sbi life", "sbi life share", "sbi life insurance"],
        peers=[],
    ),
    CompanyConfig(
        ticker="BPCL.NS",
        name="Bharat Petroleum Corp",
        short_name="BPCL",
        sector="Energy",
        sub_sector="Oil & Gas",
        keywords=["bpcl", "bpcl share", "bharat petroleum corp"],
        peers=[],
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
GROQ_MODEL = "mixtral-8x7b-32768"
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
