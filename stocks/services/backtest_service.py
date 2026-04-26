"""
stocks/services/backtest_service.py
-------------------------------------
STEP 8 — Backtesting Engine
Strategy: Moving Average Crossover (Golden Cross / Death Cross)

Signal logic:
  - When short MA (20d) crosses ABOVE long MA (50d) → BUY
  - When short MA crosses BELOW long MA → SELL

Output:
  - Trade log (entry/exit points)
  - Performance metrics (total return, max drawdown, win rate)
  - Equity curve (for charting)

Architecture: stateless function — easy to parallelise or upgrade
to more complex strategies in v2.
"""

import logging
import pandas as pd
import numpy as np
import yfinance as yf
from stocks.utils.validators import validate_symbol, validate_positive_number

logger = logging.getLogger("stocks")


class BacktestService:
    """Simulates MA crossover strategy and returns performance metrics."""

    def run(
        self,
        symbol: str,
        initial_investment: float = 10000.0,
        period: str = "2y",
        short_window: int = 20,
        long_window: int = 50,
    ) -> dict:
        symbol = validate_symbol(symbol)
        initial_investment = validate_positive_number(initial_investment, "initial_investment")

        try:
            df = yf.download(symbol, period=period, interval="1d", progress=False)
            if df.empty:
                raise ValueError(f"No data for '{symbol}'.")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df["Close"].squeeze().dropna()
            dates = close.index

            # Compute MAs
            ma_short = close.rolling(short_window).mean()
            ma_long = close.rolling(long_window).mean()

            # Generate signals
            signals = pd.Series(0, index=dates)
            signals[ma_short > ma_long] = 1  # Buy/hold
            position = signals.diff().fillna(0)

            # Simulate portfolio
            cash = initial_investment
            shares = 0.0
            trades = []
            equity_curve = []

            for i, date in enumerate(dates):
                price = float(close.iloc[i])
                sig = float(position.iloc[i])

                if sig == 1 and cash > 0:  # BUY
                    shares = cash / price
                    cash = 0.0
                    trades.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "action": "BUY",
                        "price": round(price, 2),
                        "shares": round(shares, 4),
                    })
                elif sig == -1 and shares > 0:  # SELL
                    cash = shares * price
                    profit = cash - initial_investment
                    trades.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "action": "SELL",
                        "price": round(price, 2),
                        "shares": round(shares, 4),
                        "proceeds": round(cash, 2),
                    })
                    shares = 0.0

                portfolio_value = cash + shares * price
                equity_curve.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "value": round(portfolio_value, 2),
                })

            # Final value
            final_value = cash + shares * float(close.iloc[-1])
            total_return = ((final_value - initial_investment) / initial_investment) * 100

            # Max drawdown on equity curve
            equity_values = np.array([e["value"] for e in equity_curve])
            peak = np.maximum.accumulate(equity_values)
            drawdown = (equity_values - peak) / peak
            max_dd = float(drawdown.min()) * 100

            # Win rate
            sell_trades = [t for t in trades if t["action"] == "SELL"]
            buy_prices = [trades[i - 1]["price"] for i, t in enumerate(trades) if t["action"] == "SELL"]
            wins = sum(
                1 for s, b in zip(sell_trades, buy_prices) if s["price"] > b
            )
            win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0

            return {
                "symbol": symbol,
                "strategy": f"MA Crossover ({short_window}/{long_window})",
                "period": period,
                "initial_investment": round(initial_investment, 2),
                "final_value": round(final_value, 2),
                "total_return_pct": round(total_return, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "win_rate_pct": round(win_rate, 1),
                "total_trades": len(trades),
                "trades": trades[-10:],  # Last 10 trades for display
                "equity_curve": equity_curve,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Backtest error for {symbol}: {e}", exc_info=True)
            raise RuntimeError(f"Backtest failed for '{symbol}'.")
