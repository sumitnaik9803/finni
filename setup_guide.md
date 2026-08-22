# Finni Setup Guide

Step-by-step instructions to get Finni running autonomously on GitHub Actions.

---

## Prerequisites

- A **GitHub account** (free)
- A **Google account** (for Sheets API — free)

---

## Step 1: Groq API Key (Primary LLM)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up / sign in (free, no credit card)
3. Go to **API Keys** in the left sidebar
4. Click **Create API Key**
5. Copy the key — you'll need it as a GitHub secret

> **Free tier**: 14,400 requests/day, 30 req/min (more than enough for Finni)

---

## Step 2: Google Gemini API Key (Fallback LLM)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **Get API Key** → **Create API key**
4. Select or create a Google Cloud project
5. Copy the key — you'll need it as a GitHub secret

> **Free tier**: ~15 req/min for Gemini Flash (used only when Groq fails)

---

## Step 3: Google Sheets Setup

### 3a. Create a Google Cloud Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. **Select or create a project** using the project dropdown at the top-left (next to "Google Cloud")
3. **Enable the required APIs** (easiest via the search bar at the top of the console):
   - Type **"Google Sheets API"** in the search bar → click the result → click **Enable**
   - Type **"Google Drive API"** in the search bar → click the result → click **Enable**
   > *Alternative*: Click the **☰ hamburger menu** (top-left) → look for **"APIs & Services"** (you may need to click **"More products"** at the bottom to find it) → **"Enabled APIs & services"** → **"+ ENABLE APIS AND SERVICES"**
4. **Create a Service Account**:
   - Search **"Credentials"** in the top search bar, or go to ☰ → APIs & Services → Credentials
   - Click **Create Credentials** → **Service Account**
   - Name it (e.g., "finni-bot"), click through the steps
5. On the service account page, go to the **Keys** tab
6. Click **Add Key** → **Create new key** → **JSON**
7. A JSON file will be downloaded — keep this safe

### 3b. Create the Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new spreadsheet
2. Name it (e.g., "Finni Dashboard")
3. Note the **Sheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SHEET_ID_IS_HERE/edit
   ```
4. **Share the spreadsheet** with the service account email:
   - Click **Share** on the spreadsheet
   - Paste the service account email (found in the JSON file under `client_email`, looks like `finni-bot@project-name.iam.gserviceaccount.com`)
   - Give it **Editor** access
   - Click **Send** (uncheck "Notify people" if prompted)

### 3c. Encode the Credentials

The JSON file needs to be base64-encoded for storage as a GitHub secret:

**On Windows (PowerShell)**:
```powershell
$content = Get-Content -Path "path\to\your-service-account.json" -Raw
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($content))
```

**On macOS/Linux**:
```bash
base64 -i path/to/your-service-account.json | tr -d '\n'
```

Copy the entire base64 output — that's your `GOOGLE_SHEETS_CREDENTIALS` secret.

---

## Step 4: GitHub Repository Setup

### 4a. Push the code

```bash
cd finni
git init
git add .
git commit -m "Initial Finni setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/finni.git
git push -u origin main
```

> ⚡ Make the repo **public** to get unlimited free GitHub Actions minutes.

### 4b. Add Secrets

1. Go to your repo on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key from Step 1 |
| `GEMINI_API_KEY` | Your Gemini API key from Step 2 |
| `GOOGLE_SHEETS_CREDENTIALS` | Base64-encoded service account JSON from Step 3c |
| `GOOGLE_SHEET_ID` | The spreadsheet ID from Step 3b |

### 4c. Enable GitHub Actions

1. Go to the **Actions** tab in your repo
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. The `Finni Daily Pipeline` workflow should appear

---

## Step 5: Test Run

### Option A: Manual trigger (recommended for first test)

1. Go to **Actions** → **Finni Daily Pipeline**
2. Click **Run workflow** → **Run workflow**
3. Watch the logs to ensure all 8 steps complete successfully

### Option B: Local test

```bash
# Set environment variables
$env:GROQ_API_KEY = "your-key"
$env:GEMINI_API_KEY = "your-key"
$env:GOOGLE_SHEETS_CREDENTIALS = "base64-encoded-json"
$env:GOOGLE_SHEET_ID = "your-sheet-id"

# Install dependencies
pip install -r requirements.txt

# Run
python -m src.main
```

---

## Step 6: Verify Automation

After the first successful manual run:

1. **Check the repo**: A new file should appear at `data/reports/YYYY-MM-DD.md`
2. **Check Google Sheets**: The "Daily Log" and "Dashboard" sheets should be populated
3. **Wait for cron**: The pipeline will auto-run at 6:45 AM IST on the next weekday
4. **Check Actions tab**: Verify the cron run completed successfully

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `GROQ_API_KEY not set` | Ensure the secret is named exactly `GROQ_API_KEY` in GitHub |
| `429 Too Many Requests` | Rate limit hit — the pipeline has built-in fallback to Gemini |
| `yfinance download failed` | Yahoo Finance may be temporarily down — technicals will show neutral |
| `Google Sheets connection failed` | Verify service account has Editor access to the sheet |
| `Workflow not running on schedule` | Ensure the repo is public OR you have free minutes remaining |
| `No articles found` | RSS feeds may be temporarily down — check feed URLs manually |

---

## Customization

### Add/remove companies

Edit `COMPANIES` in `src/config.py` — add a new `CompanyConfig` with the NSE ticker (`.NS` suffix), keywords, and sector.

### Change signal weights

Edit `SENTIMENT_WEIGHT` and `TECHNICAL_WEIGHT` in `src/config.py` (they should sum to 1.0).

### Change schedule

Edit the cron expression in `.github/workflows/daily_pipeline.yml`. Use [crontab.guru](https://crontab.guru) to validate.
