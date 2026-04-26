"""
stocks/services/history_service.py
------------------------------------
STEP 3 — Historical Data + Technical Indicators
Responsibilities:
  - Fetch OHLCV history via yfinance
  - Compute Moving Averages (20, 50, 200 day)
  - Compute RSI (14-period)
  - Compute MACD (12, 26, 9)
  - Return structured data ready for Recharts

Architecture note: All indicator math is done with pandas/numpy only —
no additional library needed. This keeps the dependency list lean.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from stocks.utils.cache_utils import get_cached, set_cached, make_key, HISTORY_TTL
from stocks.utils.validators import validate_symbol

logger = logging.getLogger("stocks")

PERIOD_MAP = {
    "1d": "1d", "5d": "5d", "7d": "7d", 
    "1mo": "1mo", "30d": "1mo", "60d": "2mo",
    "3mo": "3mo", "90d": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y", "max": "max"
}


class HistoryService:
    """Fetches historical OHLCV data and computes technical indicators."""

    def get_history(self, symbol: str, period: str = "30d") -> dict:
        symbol = validate_symbol(symbol)
        period = period if period in PERIOD_MAP else "30d"
        cache_key = make_key("history", symbol, period)

        cached = get_cached(cache_key)
        if cached:
            return cached

        result = self._fetch_and_compute(symbol, period)
        set_cached(cache_key, result, HISTORY_TTL)
        return result

    def _fetch_and_compute(self, symbol: str, period: str) -> dict:
        try:
            yf_period = PERIOD_MAP[period]
            df = yf.download(symbol, period=yf_period, interval="1d", progress=False)

            if df.empty:
                if "TATAMOTORS" in symbol:
                    raise ValueError(f"Historical data for '{symbol}' is currently unavailable due to the recent corporate demerger. Please view other TATA stocks like TATASTEEL.")
                raise ValueError(f"No historical data found for '{symbol}'.")

            # Flatten multi-index columns if present (yfinance 0.2+)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume",
            })
            df.index = pd.to_datetime(df.index)

            # ── Technical Indicators ──────────────────────────────
            df["ma20"] = df["close"].rolling(20).mean().round(2)
            df["ma50"] = df["close"].rolling(50).mean().round(2)
            df["ma200"] = df["close"].rolling(200).mean().round(2)
            df["rsi"] = self._compute_rsi(df["close"])
            macd_line, signal_line = self._compute_macd(df["close"])
            df["macd"] = macd_line.round(4)
            df["macd_signal"] = signal_line.round(4)
            df["macd_hist"] = (macd_line - signal_line).round(4)

            # ── Serialise to list of dicts ────────────────────────
            df = df.reset_index().rename(columns={"Date": "date"})
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            df = df.replace({np.nan: None})

            records = df.to_dict(orient="records")

            return {
                "symbol": symbol,
                "period": period,
                "count": len(records),
                "data": records,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"History fetch error for {symbol}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to retrieve history for '{symbol}'.")

    # ── Indicator Math ─────────────────────────────────────────────

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Wilder's RSI."""
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.round(2)

    @staticmethod
    def _compute_macd(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ):
        """Standard MACD."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line
