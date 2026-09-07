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
NEWS_WINDOW_HOURS = 168   # 7 days. Wide enough that thinly-covered stocks still
                          # surface something, and it inherently spans weekends.

# Cap on how many articles per company get sent to the LLM each run.
# 49 companies x this = the per-run scoring call ceiling (Gemini free tier: 1,500/day).
MAX_ARTICLES_PER_COMPANY = 8

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
RECENCY_HALF_LIFE_HOURS = 48.0  # weight halves every 48 hours
# Scaled to match NEWS_WINDOW_HOURS. The old 6h half-life was tuned for an 18h window;
# inside a 7-day window it drove a week-old article's weight to ~4e-9, meaning the extra
# days of news showed up in the report but had no effect on the score. At 48h the
# gradient spans the window usefully: 1d ≈ 0.71, 2d ≈ 0.50, 7d ≈ 0.09 — recent news
# still dominates without older news being erased entirely.


# ──────────────────────────────────────────────
# Technical Indicator Configuration
# ──────────────────────────────────────────────

# How much historical data to fetch for indicator calculation
TECHNICAL_LOOKBACK_PERIOD = "8mo"   # 8 months to ensure SMA200 has enough data
TECHNICAL_INTERVAL = "1d"           # Daily candles

# Fallback data providers, tried in order if yfinance fails: jugaad-data, then nselib.
# Both scrape nseindia.com directly and use the bare NSE symbol (no ".NS" suffix).
TECHNICAL_LOOKBACK_DAYS = 250        # Calendar days to request from fallback providers (~8mo of trading days)
NSE_FALLBACK_CHUNK_DAYS = 80         # nselib silently mis-windows requests spanning >~4 months (observed
                                      # empirically — it returns a stale/shifted date range with no error),
                                      # so fetch in short chunks and stitch them together instead.

# RSI thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Volume ratio threshold for "unusual volume" flag
VOLUME_RATIO_NOTABLE = 1.5


# ──────────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Fundamentals (screener.in)
# ──────────────────────────────────────────────

# Screener keys its company pages off the bare NSE symbol, so most tickers map
# straight through once ".NS" is stripped. A handful of listings use a different
# symbol there; add them here as they turn up (a miss is logged, not fatal).
SCREENER_URL_TEMPLATE = "https://www.screener.in/company/{symbol}/"
SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/"
SCREENER_TIMEOUT_SECONDS = 20
# Screener starts refusing partway through an unpaced 49-request sweep: the first
# 20-odd resolve, then even valid symbols (COALINDIA, HCLTECH) return nothing, and
# the search fallback resolves a URL that also fails. That is throttling, not a
# missing page. A short pause between companies costs ~40s and recovers them.
SCREENER_REQUEST_DELAY_SECONDS = 0.8
# Empty for now: LTIM was mapped to LTIMINDTREE here, but that 404s too — LTIM has no
# screener page at all, so the miss path (search, then blank cells) is the right answer.
SCREENER_SYMBOL_OVERRIDES: dict[str, str] = {}

# ──────────────────────────────────────────────
# Tickertape links (one per tracked stock)
# ──────────────────────────────────────────────

# Tickertape URLs end in ITS OWN security id, not the NSE symbol: JSWSTEEL is
# JSTL, HCLTECH is HCLT, Tata Steel is TISC. There is no rule to derive one from
# the other, so every slug below was resolved through Tickertape's search API and
# then fetched to confirm it returns HTTP 200. Re-run scripts/refresh_tickertape.py
# if a company is added or a listing changes.
#
# LTIM is the one that needed a judgement call: Tickertape's search still indexes
# only the pre-merger LTI and Mindtree, so LTIMindtree resolves under the legacy
# L&T Infotech id (LRTI). Confirmed by quote — that id prices at ~4,570, matching
# LTIM.NS, while the old Mindtree id returns no data at all.
TICKERTAPE_URL_TEMPLATE = "https://www.tickertape.in{slug}"

TICKERTAPE_SLUGS = {
    "RELIANCE":    "/stocks/reliance-industries-RELI",
    "TCS":         "/stocks/tata-consultancy-services-TCS",
    "HDFCBANK":    "/stocks/hdfc-bank-HDBK",
    "ICICIBANK":   "/stocks/icici-bank-ICBK",
    "INFY":        "/stocks/infosys-INFY",
    "ITC":         "/stocks/itc-ITC",
    "SBIN":        "/stocks/state-bank-of-india-SBI",
    "BHARTIARTL":  "/stocks/bharti-airtel-BRTI",
    "HINDUNILVR":  "/stocks/hindustan-unilever-HLL",
    "LT":          "/stocks/larsen-and-toubro-LART",
    "BAJFINANCE":  "/stocks/bajaj-finance-BJFN",
    "AXISBANK":    "/stocks/axis-bank-AXBK",
    "KOTAKBANK":   "/stocks/kotak-mahindra-bank-KTKM",
    "MARUTI":      "/stocks/maruti-suzuki-india-MRTI",
    "SUNPHARMA":   "/stocks/sun-pharmaceutical-industries-SUN",
    "ULTRACEMCO":  "/stocks/ultratech-cement-ULTC",
    "TATAMOTORS":  "/stocks/tata-motors-TAMO",
    "NTPC":        "/stocks/ntpc-NTPC",
    "TITAN":       "/stocks/titan-company-TITN",
    "ONGC":        "/stocks/oil-and-natural-gas-corporation-ONGC",
    "POWERGRID":   "/stocks/power-grid-corporation-of-india-PGRD",
    "COALINDIA":   "/stocks/coal-india-COAL",
    "ASIANPAINT":  "/stocks/asian-paints-ASPN",
    "BAJAJFINSV":  "/stocks/bajaj-finserv-BJFS",
    "ADANIENT":    "/stocks/adani-enterprises-ADEL",
    "ADANIPORTS":  "/stocks/adani-ports-and-special-economic-zone-APSE",
    "M&M":         "/stocks/mahindra-and-mahindra-MAHM",
    "WIPRO":       "/stocks/wipro-WIPR",
    "HCLTECH":     "/stocks/hcl-technologies-HCLT",
    "TATASTEEL":   "/stocks/tata-steel-TISC",
    "JSWSTEEL":    "/stocks/jsw-steel-JSTL",
    "HINDALCO":    "/stocks/hindalco-industries-HALC",
    "GRASIM":      "/stocks/grasim-industries-GRAS",
    "TECHM":       "/stocks/tech-mahindra-TEML",
    "LTIM":        "/stocks/ltimindtree-LRTI",
    "INDUSINDBK":  "/stocks/indusind-bank-INBK",
    "BAJAJ-AUTO":  "/stocks/bajaj-auto-BAJA",
    "EICHERMOT":   "/stocks/eicher-motors-EICH",
    "HEROMOTOCO":  "/stocks/hero-motocorp-HROM",
    "DRREDDY":     "/stocks/drreddys-laboratories-REDY",
    "CIPLA":       "/stocks/cipla-CIPL",
    "DIVISLAB":    "/stocks/divis-laboratories-DIVI",
    "APOLLOHOSP":  "/stocks/apollo-hospitals-enterprise-APLH",
    "BRITANNIA":   "/stocks/britannia-industries-BRIT",
    "NESTLEIND":   "/stocks/nestle-india-NEST",
    "TATACONSUM":  "/stocks/tata-consumer-products-TACN",
    "HDFCLIFE":    "/stocks/hdfc-life-insurance-company-HDFL",
    "SBILIFE":     "/stocks/sbi-life-insurance-company-SBIL",
    "BPCL":        "/stocks/bharat-petroleum-corporation-BPCL",
}


def get_tickertape_url(ticker: str) -> str:
    """
    The Tickertape page for a ticker, or "" if we have no slug for it.

    Accepts either form of the symbol ("RELIANCE" or "RELIANCE.NS") since the
    sheet stores the bare one and the pipeline carries the suffixed one.
    """
    slug = TICKERTAPE_SLUGS.get(ticker.replace(".NS", "").strip().upper())
    return TICKERTAPE_URL_TEMPLATE.format(slug=slug) if slug else ""


# ──────────────────────────────────────────────
# Event calendar (NSE corporate actions & results)
# ──────────────────────────────────────────────

# NSE serves these as plain JSON with no key and no login. They are the same feeds
# the nseindia.com corporate-filings pages are built from.
NSE_CORPORATE_ACTIONS_URL = (
    "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
)
NSE_EVENT_CALENDAR_URL = "https://www.nseindia.com/api/event-calendar"
NSE_HOLIDAY_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
NSE_REQUEST_TIMEOUT_SECONDS = 30

# How far ahead to report events. A month covers a full results cycle.
EVENT_LOOKAHEAD_DAYS = 30

# How far BACK to look, which matters more than the forward window. A past ex-date
# is the one that explains the chart in front of you: NTPC, Coal India and ONGC all
# went ex-dividend on 2-4 Sep 2026, and the 1% or so each dropped fed straight into
# their technical scores with nothing in the news to account for it. The default
# endpoint returns only the next couple of dozen rows market-wide, so the window has
# to be requested explicitly.
EVENT_LOOKBACK_DAYS = 20

# Within this many days, an event is flagged rather than merely listed.
EVENT_IMMINENT_DAYS = 3

# Articles for one company are scored in a single batched request. Summaries are
# trimmed harder than in the single-article prompt since 8 of them share one call.
BATCH_SUMMARY_CHARS = 240

# How long to wait before re-sending a batch that was refused for rate limiting.
# A 429 means "not this minute", so the wait has to clear the provider's rolling
# per-minute window — hence just over 60s rather than a token backoff.
BATCH_RETRY_DELAY_SECONDS = 65

# Provider order: each is tried in turn until one returns parseable JSON.
#
# Gemini leads because the binding free-tier constraint here is TOKENS, not requests:
#   Groq gpt-oss-120b : 30 RPM /  8,000 TPM /   200,000 tokens per day
#   Gemini Flash      : ~10 RPM /  250,000 TPM / 250-1,000 requests per day
# A scoring call costs ~480 input + up to ~1K output tokens. Groq's 8K TPM therefore
# only sustains ~5 calls/min, and its 200K TPD caps the whole day at ~100-300 articles
# — running Groq first produced a sustained 429 storm. Gemini's TPM budget is 125x
# larger and absorbs the batched workload (49 calls/run) comfortably.
# Swap the order here to put Groq back in front.
#
# Cerebras sits LAST deliberately. Groq's 200K tokens/day is ~75% spent by a single run
# (66 calls x ~2.3K on 2026-09-07), leaving no slack for a retry storm or a re-run. A
# TAIL provider only wakes once the ones ahead of it are exhausted, so on a normal day
# it is never called and therefore cannot shift a single score — it is insurance, not a
# participant. It stays dormant until CEREBRAS_API_KEY is set; no key, no attempt.
LLM_PROVIDER_ORDER = ["gemini", "groq", "cerebras"]

# Groq (fallback)
# openai/gpt-oss-120b: current production model (not preview), 131K context, native
# JSON mode, and Groq's structured-output support. Replaces allam-2-7b (a small
# Arabic-first model — a poor fit for English financial JSON, likely the cause of the
# universal Sentiment Score = 0.0 seen in every report to date).
# Free tier: 30 RPM / 1,000 RPD — plenty for ~200 scoring calls/day, but far below the
# 14,400 RPD the old llama-3.1-8b-instant advertised (that model is now deprecated).
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_MAX_RPM = 5                   # NOT the 30 RPM request cap — the real ceiling is 8,000 TPM.
                                    # At ~480 input + 1,024 reserved output tokens per call,
                                    # 5 calls/min ≈ 7,500 TPM. Setting this to 25 (the old value)
                                    # ran ~3-8x over the token budget and 429-stormed.
GROQ_MAX_TOKENS = 4096             # Sized for a BATCH, not one article. Each scored article
                                    # is ~90 tokens of JSON, so 8 of them need ~750 — and
                                    # gpt-oss is a reasoning model whose hidden reasoning also
                                    # draws on this budget. At 1024 the array was truncated
                                    # mid-object ("reasoning": "The article high...), the JSON
                                    # failed to parse, and 13 of 49 companies fell back to
                                    # per-article scoring — 8x the calls, which is what
                                    # exhausted the 200K daily token cap.
GROQ_TEMPERATURE = 0.1             # Low temp for consistent structured output
GROQ_REASONING_EFFORT = "low"      # This is a short classification task, not a proof — minimize
                                    # internal reasoning tokens rather than paying for depth we don't use.
GROQ_REASONING_FORMAT = "hidden"   # Strip the reasoning trace from the response entirely so
                                    # `response.choices[0].message.content` is JSON-only (no
                                    # markdown fences or <think> blocks to strip downstream).

# Gemini
# Google is retiring the old "AIza..." standard keys: every key AI Studio issues now
# is an *auth key* with an "AQ." prefix, bound to a service account, and the Gemini API
# rejects standard keys from September 2026. So the AQ. key is correct — what broke us
# is the ENDPOINT. Auth keys are documented against the Interactions API
# (/v1beta/interactions); the legacy models/{model}:generateContent surface answers an
# AQ. key with 401 ACCESS_TOKEN_TYPE_UNSUPPORTED. llm_scorer calls Interactions first
# and only falls back to generateContent, so both key formats work.
GEMINI_USE_INTERACTIONS_API = True
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_GENERATECONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Free-tier model names churn fast (2.0 -> 2.5 -> 3.x inside a year) and a retired
# name fails with a 404 that looks nothing like a rate limit. Worse, ListModels is not
# a reliable guide: it still advertises gemini-2.5-flash to accounts that get
# "no longer available to new users" when they actually call it. So this is a
# preference list tried in order, and a 404 moves to the next entry at runtime.
#
# The "-latest" aliases lead deliberately: they track whatever Google currently ships,
# which is the only entry that cannot go stale.
GEMINI_MODEL_PREFERENCES = [
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]
GEMINI_MODEL = "gemini-flash-latest"

# Free tier (2026): ~10-15 RPM, 250,000 TPM, 250-1,000 requests/day depending on model.
# Still ~31x Groq's 8,000 TPM, which is why Gemini leads the provider order.
GEMINI_MAX_RPM = 8
GEMINI_MAX_TOKENS = 4096           # The GROQ_MAX_TOKENS lesson above, learned twice.
                                    # gemini-3.6-flash is a THINKING model: its hidden
                                    # reasoning is drawn from this same budget before a
                                    # single character of JSON is emitted. At 1500 the
                                    # batch array came back cut off mid-object
                                    # ("reasoning": "UltraTech's aggressive entry into
                                    # wires and cables...) — 5 of the 7 unparseable
                                    # Gemini responses in the 2026-09-07 run.
GEMINI_TEMPERATURE = 0.1
GEMINI_TIMEOUT_SECONDS = 60

# Gemini answered 7 calls and then returned 429 "exceeded your current quota" 149
# times in a row — the free-tier daily allowance for this model is spent almost
# immediately. Every one of those was a wasted round trip before falling through to
# Groq. After this many consecutive failures, stop calling Gemini for the rest of
# the run; a provider that has failed 6 times running is not coming back today.
GEMINI_CONSECUTIVE_FAILURE_LIMIT = 6

# Cerebras (last-resort tail provider)
# OpenAI-compatible chat-completions surface, so it needs no new dependency — plain
# aiohttp against the same request shape Groq uses. Free tier (2026): ~1M tokens/day
# and 14,400 requests/day, which is 5x Groq's daily token budget, with an 8,192-token
# context cap that our ~2.3K batch prompts sit comfortably inside.
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = "gpt-oss-120b"    # Deliberately the SAME model family Groq serves, so a
                                    # score produced here is comparable with one produced
                                    # there. If Cerebras renames it, this one line is the
                                    # fix — the model id is printed in the run summary and
                                    # in every failure message.
CEREBRAS_MAX_RPM = 20              # Generous vs Groq: the free tier allows 14,400 req/day.
CEREBRAS_MAX_TOKENS = 4096         # Matches GROQ_MAX_TOKENS for the same batching reason.
CEREBRAS_TEMPERATURE = 0.1
CEREBRAS_TIMEOUT_SECONDS = 60
# api.cerebras.ai sits behind Cloudflare, which 403s any request carrying a default
# client User-Agent — aiohttp's and python-urllib's are both banned signatures. The
# body is a bare "error code: 1010" (browser signature banned), NOT Cerebras JSON,
# because the request never reaches Cerebras at all. Proven with a deliberately
# invalid key: default UA -> 403/1010, browser UA -> 401 "Wrong API Key". Without
# this header the provider would have failed on the one day it was needed, and the
# error would have read exactly like a rejected key.
CEREBRAS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


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


def get_cerebras_api_key() -> str:
    """
    Cerebras is optional, so this returns "" rather than raising.

    It is the tail of LLM_PROVIDER_ORDER: without a key the provider simply reports
    itself unavailable and is skipped, exactly as if it were not configured. Raising
    here would turn "no Cerebras key" into a crash for a run that never needed it.
    """
    return os.environ.get("CEREBRAS_API_KEY", "")


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
