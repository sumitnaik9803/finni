"""
Finni Events — upcoming corporate actions and results dates from NSE.

Why this exists is not only "more information". Two of these event types are a
CORRECTNESS problem for the rest of the pipeline:

  * On an ex-dividend date the price drops by roughly the dividend, mechanically.
  * On an ex-split or ex-bonus date it drops by the split ratio — a 1:5 split shows
    up as an 80% crash.

Nothing in the news feed explains that drop, so the technical score reads it as
collapse and the sentiment score has nothing to offset it. Knowing the ex-date is
what lets a reader tell "this fell" from "this was divided". That is why ex-dates
rank above every other event type here, ahead of even earnings.

The window therefore looks BACKWARD as well as forward. A dividend due in three
weeks is a note to self; one that went ex two days ago is the explanation for the
number on the screen today.

Sources (NSE's own JSON APIs, no key, no login):
  * corporate actions  -> ex-dates for dividends, splits, bonuses, rights
  * event calendar     -> board meetings, filtered to the ones that declare results

Everything fails soft: a miss returns nothing and the pipeline carries on.
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.config import (
    EVENT_LOOKAHEAD_DAYS,
    EVENT_LOOKBACK_DAYS,
    EVENT_IMMINENT_DAYS,
    NSE_CORPORATE_ACTIONS_URL,
    NSE_EVENT_CALENDAR_URL,
    NSE_HOLIDAY_URL,
    NSE_REQUEST_TIMEOUT_SECONDS,
)
from src.telemetry import telemetry

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
}

# Ex-date events, ranked by how badly they distort the price series if unnoticed.
# A split or bonus rebases the price outright; a dividend shifts it by a percent or
# two. Rights sit in between. Anything not matched here is reported but not ranked.
_ACTION_SEVERITY = [
    (re.compile(r"\bsplit\b", re.I), "SPLIT", 3),
    (re.compile(r"\bbonus\b", re.I), "BONUS", 3),
    (re.compile(r"\brights?\b", re.I), "RIGHTS", 2),
    (re.compile(r"\b(demerger|amalgamation|scheme of arrangement)\b", re.I), "RESTRUCTURE", 2),
    (re.compile(r"\bdividend\b", re.I), "DIVIDEND", 1),
]


@dataclass
class CompanyEvent:
    """One dated, upcoming event for one ticker."""
    ticker: str
    event_date: date
    kind: str             # DIVIDEND, SPLIT, BONUS, RIGHTS, RESTRUCTURE, RESULTS, OTHER
    description: str
    severity: int         # 3 rebases the price, 1 nudges it, 0 informational

    @property
    def days_away(self) -> int:
        return (self.event_date - date.today()).days

    @property
    def is_past(self) -> bool:
        return self.event_date < date.today()

    def render(self) -> str:
        when = self.event_date.isoformat()
        if self.is_past:
            return f"{self.description} (ex {when}, PASSED)"
        return f"{self.description} ({when})"


def _parse_nse_date(raw: str) -> date | None:
    """NSE serves dates as '07-Sep-2026'; a few endpoints use '07-09-2026'."""
    if not raw or raw.strip() in ("-", "null"):
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _classify(subject: str) -> tuple[str, int]:
    """Map an NSE 'subject' string onto our event kind and severity."""
    for pattern, kind, severity in _ACTION_SEVERITY:
        if pattern.search(subject or ""):
            return kind, severity
    return "OTHER", 0


class EventsFetcher:
    """Fetches recent and upcoming corporate actions and results for tracked tickers."""

    @staticmethod
    def _window_params() -> str:
        """
        The from/to query string for the reporting window.

        Without an explicit window these endpoints return only the next ~20 rows
        across the whole market, which in practice contains no large caps at all —
        the reason an unwindowed query matched none of the 49 tracked companies.
        """
        start = date.today() - timedelta(days=EVENT_LOOKBACK_DAYS)
        end = date.today() + timedelta(days=EVENT_LOOKAHEAD_DAYS)
        return (
            f"from_date={start.strftime('%d-%m-%Y')}"
            f"&to_date={end.strftime('%d-%m-%Y')}"
        )

    def _get_json(self, url: str, component: str):
        """GET one NSE JSON endpoint. Returns parsed JSON, or None on any failure."""
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=NSE_REQUEST_TIMEOUT_SECONDS) as resp:
                if resp.status != 200:
                    telemetry.fail(component, f"HTTP {resp.status}")
                    return None
                data = json.loads(resp.read().decode("utf-8", "replace"))
            telemetry.ok(component)
            return data
        except Exception as e:
            logger.warning(f"NSE {component} fetch failed: {e}")
            telemetry.fail(component, type(e).__name__)
            return None

    def fetch_corporate_actions(self, symbols: set[str]) -> list[CompanyEvent]:
        """Ex-dates for dividends, splits, bonuses and rights, for our symbols only."""
        url = f"{NSE_CORPORATE_ACTIONS_URL}&{self._window_params()}"
        rows = self._get_json(url, "nse-actions")
        if not isinstance(rows, list):
            return []

        events = []
        for row in rows:
            symbol = (row.get("symbol") or "").strip().upper()
            if symbol not in symbols:
                continue
            # The EX-date is the one that moves the price. recDate and the book-closure
            # window are settlement bookkeeping that follow it and are deliberately
            # ignored here — carrying them would report the same event three times.
            when = _parse_nse_date(row.get("exDate", ""))
            if when is None:
                continue
            subject = (row.get("subject") or "").strip()
            kind, severity = _classify(subject)
            events.append(CompanyEvent(
                ticker=symbol, event_date=when, kind=kind,
                description=subject or kind, severity=severity,
            ))
        return events

    def fetch_results_calendar(self, symbols: set[str]) -> list[CompanyEvent]:
        """
        Board meetings that will declare results, for our symbols only.

        The event calendar is mostly noise for this purpose — in a sample month, 10 of
        33 entries were "Other business matters" and 8 were fund-raising. Only the
        meetings whose stated purpose includes financial results are reliably
        price-moving, so everything else is dropped.
        """
        url = f"{NSE_EVENT_CALENDAR_URL}?{self._window_params()}"
        rows = self._get_json(url, "nse-events")
        if not isinstance(rows, list):
            return []

        events = []
        for row in rows:
            symbol = (row.get("symbol") or "").strip().upper()
            if symbol not in symbols:
                continue
            purpose = (row.get("purpose") or "")
            if "financial result" not in purpose.lower():
                continue
            when = _parse_nse_date(row.get("date", ""))
            if when is None:
                continue
            events.append(CompanyEvent(
                ticker=symbol, event_date=when, kind="RESULTS",
                description="Results", severity=2,
            ))
        return events

    def next_trading_holiday(self) -> tuple[date, str] | None:
        """The next NSE equity trading holiday, as (date, description)."""
        data = self._get_json(NSE_HOLIDAY_URL, "nse-holidays")
        if not isinstance(data, dict):
            return None
        # "CM" is the cash market segment — the one these tickers trade in.
        upcoming = []
        for row in data.get("CM", []):
            when = _parse_nse_date(row.get("tradingDate", ""))
            if when and when >= date.today():
                upcoming.append((when, (row.get("description") or "").strip()))
        return min(upcoming) if upcoming else None

    def fetch_all(self, tickers: list[str]) -> dict[str, list[CompanyEvent]]:
        """
        Every upcoming event within the lookahead window, keyed by yfinance ticker.

        NSE keys on the bare symbol, so ".NS" is stripped for matching and restored
        for the result, which is what the rest of the pipeline uses.
        """
        by_symbol = {t.replace(".NS", "").upper(): t for t in tickers}
        symbols = set(by_symbol)
        earliest = date.today() - timedelta(days=EVENT_LOOKBACK_DAYS)
        horizon = date.today() + timedelta(days=EVENT_LOOKAHEAD_DAYS)

        events = self.fetch_corporate_actions(symbols) + self.fetch_results_calendar(symbols)

        out: dict[str, list[CompanyEvent]] = {}
        for event in events:
            if not (earliest <= event.event_date <= horizon):
                continue
            ticker = by_symbol.get(event.ticker)
            if ticker is None:
                continue
            out.setdefault(ticker, []).append(event)

        # Nearest to today first in either direction, then by severity: a dividend
        # that went ex yesterday is more relevant to today's chart than one due in
        # three weeks.
        for ticker in out:
            out[ticker].sort(key=lambda e: (abs(e.days_away), -e.severity))

        logger.info(
            f"Events found for {len(out)}/{len(tickers)} companies "
            f"({EVENT_LOOKBACK_DAYS}d back to {EVENT_LOOKAHEAD_DAYS}d ahead)"
        )
        return out


def summarize(events: list[CompanyEvent]) -> str:
    """One cell's worth of events: 'Dividend - Rs 8 Per Share (2026-09-14); Results (...)'."""
    return "; ".join(e.render() for e in events[:4])


def alert(events: list[CompanyEvent]) -> str:
    """
    A short flag for events close enough to change how today's signal reads.

    A price-rebasing action (split, bonus) is called out whenever it is in the
    window at all, because the distortion it causes is large and arrives without
    warning in the price series. Everything else is flagged only once it is near.
    """
    # A rebasing action that has ALREADY happened is the most useful thing to say:
    # the drop is in the price history right now, and the technicals are reading it
    # as a sell-off. Nothing else here changes today's numbers retroactively.
    for e in events:
        if e.is_past and e.severity >= 3:
            return f"!! {e.kind} went ex {-e.days_away}d ago — price rebased, technicals distorted"
    for e in events:
        if e.is_past and e.severity >= 1:
            return f"! {e.kind} went ex {-e.days_away}d ago — part of the drop is mechanical"
    for e in events:
        if e.severity >= 3:
            return f"!! {e.kind} in {e.days_away}d — price will rebase"
    for e in events:
        if 0 <= e.days_away <= EVENT_IMMINENT_DAYS:
            if e.days_away == 0:
                return f"! {e.kind} TODAY"
            return f"! {e.kind} in {e.days_away}d"
    return ""
