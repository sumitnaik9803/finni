"""
Finni Technical Analyzer — Fetches price data and computes technical indicators.

Uses yfinance for free NSE price data (.NS suffix tickers) and pandas-ta for
indicator calculations. Produces a structured TechnicalSnapshot per stock.

Indicators: RSI(14), SMA(20/50/200), MACD(12,26,9), ATR(14), Volume ratio.
"""

import logging
from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from src.config import (
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    TECHNICAL_INTERVAL,
    TECHNICAL_LOOKBACK_PERIOD,
    VOLUME_RATIO_NOTABLE,
)

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSnapshot:
    """Point-in-time technical indicator snapshot for a stock."""
    ticker: str
    last_close: float
    prev_close: float
    day_change_pct: float           # % change from prev close

    # Indicators
    rsi_14: float
    sma_20: float
    sma_50: float
    sma_200: float
    macd_value: float
    macd_signal: float
    macd_histogram: float
    macd_crossover: str             # "BULLISH_CROSSOVER", "BEARISH_CROSSOVER", "NEUTRAL"
    atr_14: float
    volume_ratio: float             # today_vol / 20d_avg_vol

    # Derived assessments
    sma_alignment: str              # "ALL_ABOVE", "MIXED", "ALL_BELOW"
    rsi_zone: str                   # "OVERSOLD", "NEUTRAL", "OVERBOUGHT"
    volume_notable: bool            # True if volume_ratio > 1.5x
    technical_bias: str             # "BULLISH", "BEARISH", "NEUTRAL"
    technical_score: float          # -1.0 to +1.0 (quantified technical posture)


class TechnicalAnalyzer:
    """Fetches price data and computes technical indicators for stocks."""

    def analyze(self, ticker: str) -> TechnicalSnapshot:
        """
        Fetch historical data and compute all technical indicators.

        Args:
            ticker: yfinance ticker symbol (e.g., "RELIANCE.NS")

        Returns:
            TechnicalSnapshot with all indicators computed
        """
        logger.info(f"Fetching technical data for {ticker}")

        try:
            df = yf.download(
                ticker,
                period=TECHNICAL_LOOKBACK_PERIOD,
                interval=TECHNICAL_INTERVAL,
                progress=False,
                auto_adjust=True,
            )
        except Exception as e:
            logger.error(f"yfinance download failed for {ticker}: {e}")
            return self._empty_snapshot(ticker)

        if df is None or df.empty or len(df) < 50:
            logger.warning(f"Insufficient data for {ticker}: {len(df) if df is not None else 0} rows")
            return self._empty_snapshot(ticker)

        # Handle MultiIndex columns from newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Drop any duplicate column names that might cause issues
        df = df.loc[:, ~df.columns.duplicated()]

        try:
            return self._compute_indicators(ticker, df)
        except Exception as e:
            logger.error(f"Indicator computation failed for {ticker}: {e}")
            return self._empty_snapshot(ticker)

    def _compute_indicators(self, ticker: str, df: pd.DataFrame) -> TechnicalSnapshot:
        """Compute all technical indicators from price data."""
        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series(dtype=float)

        # ── Price basics ──
        last_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else last_close
        day_change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close != 0 else 0.0

        # ── RSI (14-day) ──
        rsi_series = ta.rsi(close, length=14)
        rsi_14 = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else 50.0

        # ── Simple Moving Averages ──
        sma_20_series = ta.sma(close, length=20)
        sma_50_series = ta.sma(close, length=50)
        sma_200_series = ta.sma(close, length=200)

        sma_20 = float(sma_20_series.iloc[-1]) if sma_20_series is not None and not sma_20_series.empty else last_close
        sma_50 = float(sma_50_series.iloc[-1]) if sma_50_series is not None and not sma_50_series.empty else last_close
        sma_200 = float(sma_200_series.iloc[-1]) if sma_200_series is not None and not sma_200_series.empty else last_close

        # ── MACD (12, 26, 9) ──
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            macd_cols = macd_df.columns.tolist()
            macd_value = float(macd_df.iloc[-1, 0])     # MACD line
            macd_signal_val = float(macd_df.iloc[-1, 1]) if len(macd_cols) > 1 else 0.0  # Signal line
            macd_hist = float(macd_df.iloc[-1, 2]) if len(macd_cols) > 2 else 0.0        # Histogram

            # Crossover detection: compare current and previous histogram sign
            if len(macd_df) >= 2:
                prev_hist = float(macd_df.iloc[-2, 2]) if len(macd_cols) > 2 else 0.0
                if macd_hist > 0 and prev_hist <= 0:
                    macd_crossover = "BULLISH_CROSSOVER"
                elif macd_hist < 0 and prev_hist >= 0:
                    macd_crossover = "BEARISH_CROSSOVER"
                else:
                    macd_crossover = "NEUTRAL"
            else:
                macd_crossover = "NEUTRAL"
        else:
            macd_value = 0.0
            macd_signal_val = 0.0
            macd_hist = 0.0
            macd_crossover = "NEUTRAL"

        # ── ATR (14-day) ──
        if "High" in df.columns and "Low" in df.columns:
            high = df["High"].squeeze()
            low = df["Low"].squeeze()
            atr_series = ta.atr(high, low, close, length=14)
            atr_14 = float(atr_series.iloc[-1]) if atr_series is not None and not atr_series.empty else 0.0
        else:
            atr_14 = 0.0

        # ── Volume ratio (today vs 20-day average) ──
        if not volume.empty and len(volume) >= 20:
            today_vol = float(volume.iloc[-1])
            avg_vol = float(volume.iloc[-20:].mean())
            volume_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0
        else:
            volume_ratio = 1.0

        # ── Derived assessments ──

        # SMA alignment
        above_20 = last_close > sma_20
        above_50 = last_close > sma_50
        above_200 = last_close > sma_200
        if above_20 and above_50 and above_200:
            sma_alignment = "ALL_ABOVE"
        elif not above_20 and not above_50 and not above_200:
            sma_alignment = "ALL_BELOW"
        else:
            sma_alignment = "MIXED"

        # RSI zone
        if rsi_14 < RSI_OVERSOLD:
            rsi_zone = "OVERSOLD"
        elif rsi_14 > RSI_OVERBOUGHT:
            rsi_zone = "OVERBOUGHT"
        else:
            rsi_zone = "NEUTRAL"

        # Volume notable
        volume_notable = volume_ratio > VOLUME_RATIO_NOTABLE

        # ── Technical score (point-based) ──
        score = 0.0

        # RSI contribution
        if rsi_14 < RSI_OVERSOLD:
            score += 0.20    # Oversold = bullish reversal signal
        elif rsi_14 > RSI_OVERBOUGHT:
            score -= 0.20    # Overbought = bearish signal

        # SMA contributions
        score += 0.15 if above_20 else -0.15
        score += 0.20 if above_50 else -0.20
        score += 0.25 if above_200 else -0.25

        # MACD contribution
        if macd_crossover == "BULLISH_CROSSOVER":
            score += 0.20
        elif macd_crossover == "BEARISH_CROSSOVER":
            score -= 0.20
        elif macd_hist > 0:
            score += 0.05
        elif macd_hist < 0:
            score -= 0.05

        # Clamp to [-1.0, +1.0]
        score = max(-1.0, min(1.0, score))

        # Technical bias
        if score >= 0.2:
            technical_bias = "BULLISH"
        elif score <= -0.2:
            technical_bias = "BEARISH"
        else:
            technical_bias = "NEUTRAL"

        return TechnicalSnapshot(
            ticker=ticker,
            last_close=round(last_close, 2),
            prev_close=round(prev_close, 2),
            day_change_pct=round(day_change_pct, 2),
            rsi_14=round(rsi_14, 2),
            sma_20=round(sma_20, 2),
            sma_50=round(sma_50, 2),
            sma_200=round(sma_200, 2),
            macd_value=round(macd_value, 4),
            macd_signal=round(macd_signal_val, 4),
            macd_histogram=round(macd_hist, 4),
            macd_crossover=macd_crossover,
            atr_14=round(atr_14, 2),
            volume_ratio=round(volume_ratio, 2),
            sma_alignment=sma_alignment,
            rsi_zone=rsi_zone,
            volume_notable=volume_notable,
            technical_bias=technical_bias,
            technical_score=round(score, 4),
        )

    def _empty_snapshot(self, ticker: str) -> TechnicalSnapshot:
        """Return a neutral/empty snapshot when data is unavailable."""
        return TechnicalSnapshot(
            ticker=ticker,
            last_close=0.0,
            prev_close=0.0,
            day_change_pct=0.0,
            rsi_14=50.0,
            sma_20=0.0,
            sma_50=0.0,
            sma_200=0.0,
            macd_value=0.0,
            macd_signal=0.0,
            macd_histogram=0.0,
            macd_crossover="NEUTRAL",
            atr_14=0.0,
            volume_ratio=1.0,
            sma_alignment="MIXED",
            rsi_zone="NEUTRAL",
            volume_notable=False,
            technical_bias="NEUTRAL",
            technical_score=0.0,
        )
