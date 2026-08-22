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
│  LLM Scorer      │──→ Groq (primary) + Gemini Flash (fallback)
│  (Sentiment)     │    Single-pass JSON: score, reasoning, spillover
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  Aggregator      │──→ Weighted roll-up (recency × source × impact × confidence)
└──────────────────┘
    │
    ▼                    ┌──────────────────┐
    ├────────────────────│  Technicals      │──→ yfinance + pandas-ta
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

## 📋 Tracked Companies (v1)

| Ticker | Company | Sector |
|--------|---------|--------|
| RELIANCE | Reliance Industries | Diversified (Oil/Telecom/Retail) |
| TCS | Tata Consultancy Services | IT |
| HDFCBANK | HDFC Bank | Banking |
| MARUTI | Maruti Suzuki | Automobile |
| SUNPHARMA | Sun Pharma | Pharmaceuticals |
| ITC | ITC Limited | FMCG |
| TITAN | Titan Company | Consumer Discretionary |
| BHARTIARTL | Bharti Airtel | Telecom |

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
│   ├── signal_generator.py     # Blended signal generation
│   ├── report_builder.py       # Report formatting
│   ├── sheets_publisher.py     # Google Sheets integration
│   └── main.py                 # Pipeline orchestrator
├── data/reports/               # Historical daily reports (auto-committed)
├── requirements.txt
├── setup_guide.md              # Detailed setup instructions
└── README.md
```

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
- **Groq API** (Llama 3.1 8B) — free tier, 14,400 req/day
- **Google Gemini API** (Flash) — free tier fallback
- **yfinance** + **pandas-ta** — price data & technicals
- **feedparser** + **aiohttp** — RSS ingestion
- **gspread** — Google Sheets integration
- **GitHub Actions** — free cron scheduling (public repo)
