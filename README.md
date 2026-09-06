# 📊 Finni — Autonomous Indian Stock Sentiment & Signal Tool

Finni is a fully autonomous tool that analyzes Indian stock market companies using **news sentiment** (via LLM) combined with **technical indicators**, producing a daily report with **buy/sell-style signals** before the 9:00 AM market open.

> ⚠️ **Disclaimer**: Finni produces informational signals, NOT financial advice. Signals are rule-based heuristics derived from public news sentiment and basic technical indicators. They are NOT recommendations to trade.

## 🏗️ Architecture

```
RSS Feeds (ET, BS, Mint, Google News)
    │
    ▼
┌──────────────────┐
│  News Fetcher    │──→ 18-hour window, dedup, company mapping
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  LLM Scorer      │──→ Groq gpt-oss-120b (primary) + Gemini Flash (fallback)
│  (Sentiment)     │    Single-pass JSON: score, reasoning, spillover
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  Aggregator      │──→ Weighted roll-up (recency × source × impact × confidence)
└──────────────────┘
    │
    ▼                    ┌──────────────────┐
    ├────────────────────│  Technicals      │──→ yfinance → jugaad-data → nselib
    │                    │  (Price Data)    │    RSI, SMAs, MACD, ATR, Volume
    │                    └──────────────────┘
    ▼
┌──────────────────┐
│  Signal          │──→ 55% Sentiment + 45% Technical
│  Generator       │    7-level signals: STRONG SELL → STRONG BUY
└──────────────────┘
    │
    ▼
┌──────────────────┐     ┌──────────────────┐
│  Report Builder  │────→│  Google Sheets   │
│  (Markdown)      │     │  (Dashboard)     │
└──────────────────┘     └──────────────────┘
```

## 📋 Tracked Companies

Finni tracks **49 NSE large-caps** spanning Financials, IT, Auto, FMCG, Energy,
Healthcare, Materials, Industrials, Telecom and Consumer Discretionary — including
Reliance, TCS, HDFC Bank, ICICI Bank, Infosys, SBI, ITC, Bharti Airtel, L&T,
Maruti Suzuki, Sun Pharma, Tata Motors, Titan and Adani Enterprises.

The authoritative list is `COMPANIES` in [src/config.py](src/config.py) — edit that
to add or remove a stock.

## ⏰ Schedule

Runs automatically via GitHub Actions:
- **When**: Weekdays (Mon-Fri) at **6:45 AM IST** (1:15 AM UTC)
- **Runtime**: ~15-30 minutes
- **Output**: Report ready before 9:00 AM market open

## 🚀 Setup

See [setup_guide.md](setup_guide.md) for detailed setup instructions:

1. **Fork/clone** this repo
2. Get **API keys** (Groq, Gemini, Google Sheets) — all free tier
3. Add keys as **GitHub Actions secrets**
4. **Enable** GitHub Actions on your repo
5. Reports start generating automatically

## 🏃 Manual Run

```bash
# Set environment variables
export GROQ_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
export GOOGLE_SHEETS_CREDENTIALS="base64-encoded-json"
export GOOGLE_SHEET_ID="your-sheet-id"

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python -m src.main
```

## 📂 Project Structure

```
finni/
├── .github/workflows/
│   └── daily_pipeline.yml      # GitHub Actions cron workflow
├── src/
│   ├── config.py               # Company taxonomy & constants
│   ├── news_fetcher.py         # RSS news ingestion
│   ├── llm_scorer.py           # LLM sentiment scoring
│   ├── aggregator.py           # Weighted sentiment aggregation
│   ├── technicals.py           # Price data & technical indicators
│   ├── fundamentals.py         # screener.in valuation ratios
│   ├── signal_generator.py     # Blended signal generation
│   ├── pattern_analyzer.py     # 14-day rolling sector pattern analysis
│   ├── report_builder.py       # Report formatting
│   ├── sheets_publisher.py     # Google Sheets integration
│   ├── telemetry.py            # Per-dependency call tally (run summary)
│   └── main.py                 # Pipeline orchestrator
├── scripts/
│   └── check_gemini.py         # Diagnose a Gemini key against both API surfaces
├── data/reports/               # Historical daily reports (auto-committed)
├── requirements.txt
├── setup_guide.md              # Detailed setup instructions
└── README.md
```

## 🔍 Debugging a Run

Every run ends with a summary of **all external calls**, grouped by dependency, so
you can see at a glance what worked and how much of the run each thing carried:

```
 LLM
   Gemini             47 ok     1 failed   [98% success]
        via: interactions/gemini-flash-latest x47
        model=gemini-flash-latest  endpoint=interactions
        why: HTTP 404 (model retired) x1
   Groq                2 ok     1 failed   [67% success]
        why: 429 daily quota exhausted x1
 MARKET DATA
   yfinance           45 ok     4 failed   [92% success]
   jugaad-data         4 ok     0 failed   [100% success]
```

It prints even when the pipeline crashes — a failed run is exactly the one whose
call tally you need.

**Deeper digging:**

| Want to see | Do this |
|---|---|
| Every LLM prompt and raw response | `FINNI_DEBUG_LLM=1` before running |
| Whether a Gemini key works, and on which endpoint | `python scripts/check_gemini.py $GEMINI_API_KEY` |

### Gemini API keys

Google AI Studio now issues only **auth keys** (`AQ.` prefix); the old `AIza`
standard keys are rejected from September 2026. Auth keys work against the
**Interactions API**, not the legacy `generateContent` endpoint — calling the wrong
one returns `401 ACCESS_TOKEN_TYPE_UNSUPPORTED`, which looks like a bad key but
isn't. Finni tries Interactions first and falls back automatically, so both key
formats work.

Free-tier model names are also retired on a months-long cycle, and `ListModels`
still advertises models that 404 when you call them. `GEMINI_MODEL_PREFERENCES` in
[src/config.py](src/config.py) is therefore a list tried in order, led by the
self-updating `-latest` aliases; a 404 moves to the next candidate mid-run.

## 📊 Signal Legend

| Signal | Score Range | Meaning |
|--------|-----------|---------|
| 🟢 STRONG BUY | +0.50 to +1.00 | Strong positive sentiment + bullish technicals |
| 🔵 BUY | +0.25 to +0.50 | Positive sentiment and/or bullish technicals |
| ⬆️ LEAN BULLISH | +0.10 to +0.25 | Slight positive lean |
| ⚪ NEUTRAL | -0.10 to +0.10 | Mixed or insufficient signal |
| ⬇️ LEAN BEARISH | -0.25 to -0.10 | Slight negative lean |
| 🔴 SELL | -0.50 to -0.25 | Negative sentiment and/or bearish technicals |
| 🔴 STRONG SELL | -1.00 to -0.50 | Strongly negative sentiment + bearish technicals |

## 🔧 Tech Stack

All free / open-source:
- **Python 3.12**
- **Groq API** (`openai/gpt-oss-120b`) — free tier, 30 req/min, 1,000 req/day
- **Google Gemini API** (Flash) — free tier fallback
- **yfinance** + **jugaad-data** + **nselib** — price data (3-tier fallback)
- **pandas-ta** — technical indicators
- **feedparser** + **aiohttp** — RSS ingestion
- **gspread** — Google Sheets integration
- **GitHub Actions** — free cron scheduling (public repo)
