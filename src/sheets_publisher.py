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

from src.config import (
    get_google_sheet_id,
    get_google_sheets_credentials,
    get_tickertape_url,
)
from src.telemetry import telemetry

logger = logging.getLogger(__name__)


class SheetsPublisher:
    """Publishes Finni reports to Google Sheets."""

    # Sheet names
    DAILY_LOG_SHEET = "Daily Log"
    DASHBOARD_SHEET = "Dashboard"

    # The link column sits at D, so adding it to an existing sheet means shifting
    # every column from D onward one to the right rather than just rewriting row 1.
    LINK_HEADER = "link"
    LINK_COLUMN = 4          # 1-based, as gspread counts columns

    # Column headers for the Daily Log sheet
    DAILY_LOG_HEADERS = [
        "Date", "Rank", "Ticker", "link", "Company", "Signal",
        "Blended Score", "Sentiment Score", "Sentiment Label",
        "Technical Score", "Technical Bias",
        "Last Close", "Day Change %", "RSI", "SMA Alignment", "MACD",
        "Articles", "Top Event", "Key Reasoning", "Volume Notable",
        "All Headlines",
        "P/E", "ROCE %", "ROE %", "Div Yield %",
        "Upcoming Events", "Event Alert",
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
        except Exception as e:
            logger.error("Skipping Google Sheets publish — connection failed")
            telemetry.fail("sheets", f"connect: {type(e).__name__}")
            return

        # Publish to Daily Log
        try:
            self._append_daily_log(report["sheets_data"])
            telemetry.ok("sheets", "Daily Log")
        except Exception as e:
            logger.error(f"Failed to update Daily Log sheet: {e}")
            telemetry.fail("sheets", f"Daily Log: {type(e).__name__}")

        # Publish to Dashboard
        try:
            self._update_dashboard(report["dashboard_data"])
            telemetry.ok("sheets", "Dashboard")
        except Exception as e:
            logger.error(f"Failed to update Dashboard sheet: {e}")
            telemetry.fail("sheets", f"Dashboard: {type(e).__name__}")

    def _append_daily_log(self, rows: list[dict]):
        """Append rows to the Daily Log sheet."""
        sheet = self._get_or_create_sheet(self.DAILY_LOG_SHEET)

        # Check if headers exist
        existing = sheet.get_all_values()

        # A sheet written before the link column existed has its data one column to
        # the left of where the headers now say it should be. Shift it before doing
        # anything else, or every row from D onward would be silently mislabelled.
        if existing and self._insert_link_column(sheet, existing):
            existing = sheet.get_all_values()

        if not existing:
            # Write headers first
            sheet.append_row(self.DAILY_LOG_HEADERS, value_input_option="RAW")
            logger.info("Wrote Daily Log headers")
        elif existing[0] == self.DAILY_LOG_HEADERS:
            pass  # Header row is already correct
        elif self._is_header_row(existing[0]):
            # Stale header row — a column was added or renamed since this sheet was
            # created. Rewrite row 1 in place. Data rows are left untouched.
            last_cell = gspread.utils.rowcol_to_a1(1, len(self.DAILY_LOG_HEADERS))
            sheet.update(
                values=[self.DAILY_LOG_HEADERS],
                range_name=f"A1:{last_cell}",
                value_input_option="RAW",
            )
            logger.info(
                f"Updated Daily Log headers ({len(existing[0])} -> "
                f"{len(self.DAILY_LOG_HEADERS)} columns)"
            )
        else:
            # The sheet starts straight into data with no header row at all. INSERT a
            # header above it — overwriting row 1 here would destroy a real data row.
            sheet.insert_row(self.DAILY_LOG_HEADERS, index=1, value_input_option="RAW")
            logger.info("Inserted missing Daily Log header row above existing data")

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

    def _insert_link_column(self, sheet, existing: list[list[str]]) -> bool:
        """
        Add the link column to a sheet that predates it, and backfill history.

        Inserting a column in the MIDDLE of a populated sheet is the only safe way
        to do this: simply rewriting row 1 would leave every existing data row one
        column left of its new header, so Company would be read as link, Signal as
        Company, and so on all the way to the end.

        Idempotent — it returns False and touches nothing once the column is there,
        so a re-run cannot insert a second one.
        """
        header = existing[0]
        if self.LINK_HEADER in header:
            return False
        if not self._is_header_row(header):
            # No header at all; the caller inserts a full, already-correct one.
            return False

        row_count = len(existing)
        sheet.insert_cols([[""] * row_count], col=self.LINK_COLUMN)

        # Backfill from the Ticker already in column C, which the insert did not move.
        column = [self.LINK_HEADER]
        filled = 0
        for row in existing[1:]:
            ticker = row[2].strip() if len(row) > 2 else ""
            url = get_tickertape_url(ticker) if ticker else ""
            filled += bool(url)
            column.append(url)

        sheet.update(
            values=[[value] for value in column],
            range_name=f"D1:D{row_count}",
            value_input_option="USER_ENTERED",
        )
        logger.info(
            f"Inserted the link column at D and backfilled {filled} of "
            f"{row_count - 1} existing rows"
        )
        return True

    @classmethod
    def _is_header_row(cls, row: list[str]) -> bool:
        """
        True if this row is a header rather than data. The first column is "Date":
        a header row holds that literal label, a data row holds an actual date
        ("2026-08-26"). Used to avoid overwriting real data on a header-less sheet.
        """
        if not row:
            return False
        return row[0].strip().lower() == cls.DAILY_LOG_HEADERS[0].strip().lower()

    def _get_or_create_sheet(self, title: str) -> gspread.Worksheet:
        """Get an existing worksheet by title, or create it."""
        try:
            return self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info(f"Creating worksheet: {title}")
            return self._spreadsheet.add_worksheet(title=title, rows=500, cols=20)
