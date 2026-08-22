"""
Finni Google Sheets Publisher — Pushes daily report data to Google Sheets.

Uses gspread with a service account for authentication.
Manages two sheets:
1. "Daily Log" — append-only historical record (one row per stock per day)
2. "Dashboard" — overwritten daily with the latest snapshot
"""

import base64
import json
import logging

import gspread

from src.config import get_google_sheet_id, get_google_sheets_credentials

logger = logging.getLogger(__name__)


class SheetsPublisher:
    """Publishes Finni reports to Google Sheets."""

    # Sheet names
    DAILY_LOG_SHEET = "Daily Log"
    DASHBOARD_SHEET = "Dashboard"

    # Column headers for the Daily Log sheet
    DAILY_LOG_HEADERS = [
        "Date", "Rank", "Ticker", "Company", "Signal",
        "Blended Score", "Sentiment Score", "Sentiment Label",
        "Technical Score", "Technical Bias",
        "Last Close", "Day Change %", "RSI", "SMA Alignment", "MACD",
        "Articles", "Top Event", "Key Reasoning", "Volume Notable",
    ]

    def __init__(self):
        self._gc = None
        self._spreadsheet = None

    def _connect(self):
        """Initialize the gspread connection with service account credentials."""
        if self._gc is not None:
            return

        try:
            creds_b64 = get_google_sheets_credentials()
            creds_json = json.loads(base64.b64decode(creds_b64))
            self._gc = gspread.service_account_from_dict(creds_json)
            self._spreadsheet = self._gc.open_by_key(get_google_sheet_id())
            logger.info(f"Connected to Google Sheet: {self._spreadsheet.title}")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise

    def publish_daily(self, report: dict):
        """
        Publish the daily report to Google Sheets.

        Args:
            report: dict from ReportBuilder.build() containing:
                - sheets_data: list[dict] for Daily Log
                - dashboard_data: dict for Dashboard
        """
        try:
            self._connect()
        except Exception:
            logger.error("Skipping Google Sheets publish — connection failed")
            return

        # Publish to Daily Log
        try:
            self._append_daily_log(report["sheets_data"])
        except Exception as e:
            logger.error(f"Failed to update Daily Log sheet: {e}")

        # Publish to Dashboard
        try:
            self._update_dashboard(report["dashboard_data"])
        except Exception as e:
            logger.error(f"Failed to update Dashboard sheet: {e}")

    def _append_daily_log(self, rows: list[dict]):
        """Append rows to the Daily Log sheet."""
        sheet = self._get_or_create_sheet(self.DAILY_LOG_SHEET)

        # Check if headers exist
        existing = sheet.get_all_values()
        if not existing:
            # Write headers first
            sheet.append_row(self.DAILY_LOG_HEADERS, value_input_option="RAW")
            logger.info("Wrote Daily Log headers")

        # Append each stock's row
        for row_data in rows:
            row = [row_data.get(h, "") for h in self.DAILY_LOG_HEADERS]
            sheet.append_row(row, value_input_option="USER_ENTERED")

        logger.info(f"Appended {len(rows)} rows to Daily Log")

    def _update_dashboard(self, dashboard: dict):
        """Overwrite the Dashboard sheet with current snapshot."""
        sheet = self._get_or_create_sheet(self.DASHBOARD_SHEET)

        # Clear existing content
        sheet.clear()

        # Build the dashboard layout
        rows_to_write = []

        # ── Header Section ──
        header = dashboard["header"]
        rows_to_write.append(["📊 Finni Dashboard", "", "", "", "", "", "", ""])
        rows_to_write.append([
            f"Report Date: {header['report_date']}",
            f"Generated: {header['generated_at']}",
            f"Runtime: {header['runtime']}",
            f"Total Articles: {header['total_articles']}",
            f"Stocks: {header['stocks_analyzed']}",
            "", "", "",
        ])
        rows_to_write.append([""] * 8)  # Spacer

        # ── Rankings Table ──
        rows_to_write.append(["Rank", "Ticker", "Signal", "Blended", "Sentiment", "Technical", "Last Close", "Top Driver"])

        for r in dashboard["rankings"]:
            rows_to_write.append([
                r["rank"],
                r["ticker"],
                r["signal"],
                r["blended"],
                r["sentiment"],
                r["technical"],
                r["last_close"],
                r["top_driver"],
            ])

        rows_to_write.append([""] * 8)  # Spacer

        # ── Sector Insights ──
        if dashboard.get("sector_insights"):
            rows_to_write.append(["📈 Sector Insights", "", "", "", "", "", "", ""])
            for insight in dashboard["sector_insights"]:
                rows_to_write.append([insight, "", "", "", "", "", "", ""])

        # Write all at once (batch update for speed)
        sheet.update(
            values=rows_to_write,
            range_name=f"A1:H{len(rows_to_write)}",
            value_input_option="USER_ENTERED",
        )

        logger.info("Dashboard sheet updated")

    def _get_or_create_sheet(self, title: str) -> gspread.Worksheet:
        """Get an existing worksheet by title, or create it."""
        try:
            return self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info(f"Creating worksheet: {title}")
            return self._spreadsheet.add_worksheet(title=title, rows=500, cols=20)
