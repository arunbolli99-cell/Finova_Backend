"""
stocks/services/portfolio_service.py
--------------------------------------
STEP 9 — Portfolio Analyzer

Manages a user's stock portfolio (in-memory + DB).
Features:
  - Calculate current value, P&L per holding
  - Sector distribution (fetched from yfinance info)
  - Diversification analysis (Herfindahl-Hirschman Index)
  - Risk Metrics: Beta, Volatility, Correlation
  - Over-exposure warnings (>30% in any sector)
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from stocks.utils.cache_utils import get_cached, set_cached, make_key, STOCK_PRICE_TTL
from stocks.utils.validators import validate_symbol, validate_positive_number

logger = logging.getLogger("stocks")

OVEREXPOSURE_THRESHOLD = 0.30
SECTOR_TTL = 86400           # 24 hours — sectors are static
BENCHMARK_TTL = 3600         # 1 hour
PORTFOLIO_HISTORY_TTL = 3600 # 1 hour

class PortfolioService:
    """Computes portfolio metrics for a list of holdings."""

    def analyse(self, holdings: list[dict]) -> dict:
        if not holdings:
            return {
                "holdings": [],
                "summary": {
                    "total_invested": 0,
                    "total_current_value": 0,
                    "total_pnl": 0,
                    "total_pnl_pct": 0,
                    "num_holdings": 0,
                    "diversification_score": 0,
                    "win_ratio": 0,
                    "top_asset_concentration": {"symbol": "N/A", "weight": 0},
                    "risk_profile": {"beta": 1.0, "volatility": "Low", "correlation": 0}
                },
                "sector_distribution": {},
                "warnings": [],
                "total_history": [],
            }

        enriched = []
        total_invested = 0.0
        total_current = 0.0
        sector_map: dict[str, float] = {}
        wins = 0

        # BATCH FETCH PRICES AND DATA
        symbols = [validate_symbol(h.get("symbol", "")) for h in holdings]
        prices_df = self._batch_fetch_prices(symbols)
        
        for h in holdings:
            symbol = validate_symbol(h.get("symbol", ""))
            quantity = validate_positive_number(h.get("quantity", 0), "quantity")
            avg_price = validate_positive_number(h.get("avg_buy_price", 0), "avg_buy_price")

            # GET PRICE AND SECTOR (Optimized)
            price_data = prices_df.get(symbol, {"price": avg_price, "day_change_pct": 0})
            current_price = price_data["price"]
            day_change_pct = price_data["day_change_pct"]
            sector = self._get_sector(symbol)

            invested = quantity * avg_price
            current_val = quantity * current_price
            pnl = current_val - invested
            pnl_pct = (pnl / invested) * 100 if invested else 0

            if pnl > 0: wins += 1
            total_invested += invested
            total_current += current_val

            s = sector or "Unknown"
            sector_map[s] = sector_map.get(s, 0) + current_val

            enriched.append({
                "symbol": symbol,
                "quantity": quantity,
                "avg_buy_price": round(avg_price, 2),
                "current_price": round(current_price, 2),
                "day_change_pct": round(day_change_pct, 2),
                "invested_value": round(invested, 2),
                "current_value": round(current_val, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "sector": s,
                "weight": 0 
            })

        # Calculate weights and concentration
        max_weight = 0
        top_asset = ""
        for h in enriched:
            h["weight"] = round((h["current_value"] / total_current) * 100, 2)
            if h["weight"] > max_weight:
                max_weight = h["weight"]
                top_asset = h["symbol"]

        # Portfolio-level metrics
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

        # Sector distribution %
        sector_distribution = {
            s: round((v / total_current) * 100, 2)
            for s, v in sector_map.items()
        }

        # Diversification score
        weights = [v / total_current for v in sector_map.values()]
        hhi = sum(w ** 2 for w in weights)
        n = len(sector_map)
        diversification_score = round((1 - hhi) / (1 - 1 / max(n, 2)) * 100, 1) if n > 1 else 0

        # Risk Intelligence (Beta, Volatility)
        history_data = self._calculate_total_history(holdings)
        risk_metrics = self._calculate_risk_metrics(history_data)

        # Warnings
        warnings = []
        for sector, pct in sector_distribution.items():
            if pct / 100 >= OVEREXPOSURE_THRESHOLD:
                warnings.append(f"⚠️ Over-exposed to {sector} sector ({pct:.1f}% of portfolio)")
        if n < 3:
            warnings.append("⚠️ Portfolio is under-diversified. Consider adding more sectors.")

        return {
            "holdings": enriched,
            "summary": {
                "total_invested": round(total_invested, 2),
                "total_current_value": round(total_current, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "num_holdings": len(enriched),
                "diversification_score": diversification_score,
                "win_ratio": round((wins / len(enriched)) * 100, 1) if enriched else 0,
                "top_asset_concentration": {"symbol": top_asset, "weight": max_weight},
                "risk_profile": risk_metrics
            },
            "sector_distribution": sector_distribution,
            "warnings": warnings,
            "total_history": history_data,
        }

    def _calculate_risk_metrics(self, portfolio_history: list[dict]) -> dict:
        if len(portfolio_history) < 5:
            return {"beta": 1.0, "volatility": "Low", "correlation": 0}

        try:
            # Cache benchmark data
            cache_key = make_key("benchmark_data", "NSEI")
            bench = get_cached(cache_key)
            if not bench:
                logger.info("Fetching fresh benchmark data (^NSEI)")
                bench_raw = yf.download("^NSEI", period="1mo", progress=False, threads=False)
                if bench_raw.empty: return {"beta": 1.0, "volatility": "Moderate", "correlation": 0}
                
                # Robust extraction of 'Close' column
                if 'Close' in bench_raw.columns:
                    bench_series = bench_raw['Close'].copy()
                else:
                    try: 
                        bench_series = bench_raw.xs('Close', axis=1, level=0).copy()
                    except: 
                        return {"beta": 1.0, "volatility": "Moderate", "correlation": 0}
                
                # Ensure it's a Series then convert to DataFrame with specific column name
                if isinstance(bench_series, pd.DataFrame):
                    bench_series = bench_series.iloc[:, 0]
                
                bench_df = pd.DataFrame(bench_series)
                bench_df.columns = ['^NSEI']
                bench_df.index = bench_df.index.strftime('%Y-%m-%d')
                
                set_cached(cache_key, bench_df.to_dict(), BENCHMARK_TTL)
                bench = bench_df
            else:
                bench = pd.DataFrame.from_dict(bench)

            port_df = pd.DataFrame(portfolio_history).set_index("date")
            bench_df = bench.copy()
            
            # Ensure index types match for concatenation
            combined = pd.concat([port_df, bench_df], axis=1).dropna()
            if combined.empty or len(combined) < 2:
                return {"beta": 1.0, "volatility": "Moderate", "correlation": 0}
                
            combined.columns = ['portfolio', 'market']
            returns = combined.pct_change().dropna()
            
            if returns.empty or len(returns) < 2:
                return {"beta": 1.0, "volatility": "Moderate", "correlation": 0}

            vol = returns['portfolio'].std() * np.sqrt(252)
            risk_level = "Low" if vol < 0.15 else "Moderate" if vol < 0.30 else "High"
            
            # Beta calculation using covariance matrix
            cov_matrix = np.cov(returns['portfolio'], returns['market'])
            if cov_matrix.shape == (2, 2) and cov_matrix[1, 1] != 0:
                beta = cov_matrix[0, 1] / cov_matrix[1, 1]
                correlation = returns['portfolio'].corr(returns['market'])
            else:
                beta, correlation = 1.0, 0.5

            return {
                "beta": round(float(beta), 2),
                "volatility_score": round(float(vol) * 100, 1),
                "volatility": risk_level,
                "market_correlation": round(float(correlation), 2)
            }
        except Exception as e:
            logger.error(f"Risk metric error: {e}")
            return {"beta": 1.0, "volatility": "Moderate", "correlation": 0}

    def _calculate_total_history(self, holdings: list[dict], period: str = "1mo") -> list[dict]:
        if not holdings: return []
        
        # Cache total history for the specific set of holdings
        holdings_id = ":".join(sorted([f"{h['symbol']}_{h['quantity']}" for h in holdings]))
        cache_key = make_key("portfolio_total_history", holdings_id, period)
        cached = get_cached(cache_key)
        if cached: return cached

        raw_symbols = [h.get("symbol") for h in holdings]
        sanitized_symbols = [self._sanitize_symbol(s) for s in raw_symbols]
        qty_map = {self._sanitize_symbol(h.get("symbol")): h.get("quantity", 0) for h in holdings}
        
        try:
            data = yf.download(sanitized_symbols, period=period, group_by='ticker', progress=False, threads=False)
            if data.empty: return []

            # Extract Close prices robustly
            if len(sanitized_symbols) > 1:
                try:
                    close_prices = data.xs('Close', axis=1, level=1)
                except:
                    # Fallback if MultiIndex is slightly different
                    try: close_prices = data.xs('Close', axis=1, level=0)
                    except: return []
            else:
                # Single ticker handling
                if 'Close' in data.columns: close_prices = data[['Close']]
                else: return []

            history_df = close_prices.copy()
            
            # Aggregate total value across all symbols
            for symbol in history_df.columns:
                sanitized_s = str(symbol).upper()
                if sanitized_s in qty_map:
                    history_df[symbol] = pd.to_numeric(history_df[symbol], errors='coerce') * qty_map[sanitized_s]
                elif sanitized_s.split('.')[0] in qty_map:
                     # Check without .NS
                     history_df[symbol] = pd.to_numeric(history_df[symbol], errors='coerce') * qty_map[sanitized_s.split('.')[0]]
            
            total_history_series = history_df.sum(axis=1, skipna=True)
            result = [
                {"date": date.strftime("%Y-%m-%d"), "value": round(float(val), 2)}
                for date, val in total_history_series.items() if not pd.isna(val)
            ]
            set_cached(cache_key, result, PORTFOLIO_HISTORY_TTL)
            return result
        except Exception as e:
            logger.error(f"History aggregation error: {e}")
            return []

    def _batch_fetch_prices(self, symbols: list[str]) -> dict:
        """Fetch current prices for all symbols in one hit using yf.download."""
        if not symbols: return {}
        
        sanitized = [self._sanitize_symbol(s) for s in symbols]
        try:
            # Download 1 day of 1m data to get latest price and close
            data = yf.download(sanitized, period="1d", interval="1m", progress=False, threads=True)
            if data.empty: return {}
            
            results = {}
            for s in sanitized:
                try:
                    # Handle single vs multi-ticker dataframe
                    if isinstance(data.columns, pd.MultiIndex):
                        s_data = data.xs(s, axis=1, level=1)
                    else:
                        s_data = data
                    
                    if s_data.empty: continue
                    
                    current_price = float(s_data['Close'].iloc[-1])
                    open_price = float(s_data['Open'].iloc[0])
                    change_pct = ((current_price - open_price) / open_price * 100) if open_price else 0
                    
                    # Store by original symbol and sanitized symbol
                    results[s] = {"price": current_price, "day_change_pct": change_pct}
                    # Also map back to original symbols if they were missing .NS
                    for original in symbols:
                        if self._sanitize_symbol(original) == s:
                            results[original] = results[s]
                except:
                    continue
            return results
        except Exception as e:
            logger.error(f"Batch fetch error: {e}")
            return {}

    def _get_sector(self, symbol: str) -> str:
        """Fetches sector with long-term caching."""
        cache_key = make_key("stock_sector", symbol)
        cached = get_cached(cache_key)
        if cached: return cached

        try:
            sanitized = self._sanitize_symbol(symbol)
            ticker = yf.Ticker(sanitized)
            sector = ticker.info.get("sector", "Unknown")
            set_cached(cache_key, sector, SECTOR_TTL)
            return sector
        except:
            return "Unknown"

    def _sanitize_symbol(self, symbol: str) -> str:
        if not symbol: return ""
        symbol = str(symbol).strip().upper()
        if "." not in symbol: return f"{symbol}.NS"
        return symbol
