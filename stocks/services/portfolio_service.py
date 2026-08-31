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
        symbols = []
        for h in holdings:
            sym = str(h.get("symbol", "")).strip()
            if sym:
                try:
                    symbols.append(validate_symbol(sym))
                except Exception:
                    symbols.append(self._sanitize_symbol(sym))

        prices_df = self._batch_fetch_prices(symbols)
        
        for h in holdings:
            raw_sym = str(h.get("symbol", "")).strip()
            if not raw_sym:
                continue
            try:
                symbol = validate_symbol(raw_sym)
            except Exception:
                symbol = self._sanitize_symbol(raw_sym)

            try:
                quantity = float(h.get("quantity", 1))
                if quantity <= 0:
                    quantity = 1.0
            except (TypeError, ValueError):
                quantity = 1.0

            try:
                avg_price = float(h.get("avg_buy_price", 0))
                if avg_price < 0 or np.isnan(avg_price):
                    avg_price = 0.0
            except (TypeError, ValueError):
                avg_price = 0.0

            # GET PRICE AND SECTOR (Optimized & NaN safe)
            price_data = prices_df.get(symbol) or prices_df.get(self._sanitize_symbol(symbol)) or {}
            current_price = price_data.get("price")
            if current_price is None or np.isnan(current_price) or current_price <= 0:
                current_price = avg_price if avg_price > 0 else 1.0

            day_change_pct = price_data.get("day_change_pct", 0.0)
            if day_change_pct is None or np.isnan(day_change_pct):
                day_change_pct = 0.0

            sector = self._get_sector(symbol)

            invested = quantity * avg_price
            current_val = quantity * current_price
            pnl = current_val - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

            if pnl > 0: wins += 1
            total_invested += invested
            total_current += current_val

            s = sector or "Unknown"
            sector_map[s] = sector_map.get(s, 0.0) + current_val

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
                "weight": 0.0 
            })

        # Calculate weights and concentration
        max_weight = 0.0
        top_asset = ""
        for h in enriched:
            h["weight"] = round((h["current_value"] / total_current * 100), 2) if total_current > 0 else 0.0
            if np.isnan(h["weight"]):
                h["weight"] = 0.0
            if h["weight"] > max_weight:
                max_weight = h["weight"]
                top_asset = h["symbol"]

        # Portfolio-level metrics
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
        if np.isnan(total_pnl_pct):
            total_pnl_pct = 0.0

        # Sector distribution %
        sector_distribution = {
            s: round((v / total_current * 100), 2) if total_current > 0 else 0.0
            for s, v in sector_map.items()
        }
        for s, v in list(sector_distribution.items()):
            if np.isnan(v):
                sector_distribution[s] = 0.0

        # Diversification score
        weights = [(v / total_current) for v in sector_map.values()] if total_current > 0 else []
        hhi = sum(w ** 2 for w in weights) if weights else 1.0
        n = len(sector_map)
        diversification_score = round((1 - hhi) / (1 - 1 / max(n, 2)) * 100, 1) if n > 1 else 0.0
        if np.isnan(diversification_score):
            diversification_score = 0.0

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

        response = {
            "holdings": enriched,
            "summary": {
                "total_invested": round(total_invested, 2),
                "total_current_value": round(total_current, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "num_holdings": len(enriched),
                "diversification_score": diversification_score,
                "win_ratio": round((wins / len(enriched)) * 100, 1) if enriched else 0.0,
                "top_asset_concentration": {"symbol": top_asset or "N/A", "weight": max_weight},
                "risk_profile": risk_metrics
            },
            "sector_distribution": sector_distribution,
            "warnings": warnings,
            "total_history": history_data,
        }
        return self._sanitize_response(response)

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
                    
                    if s_data.empty or 'Close' not in s_data.columns:
                        continue
                    
                    # Ensure we grab the last non-NaN close price
                    valid_closes = s_data['Close'].dropna()
                    if valid_closes.empty:
                        continue
                    current_price = float(valid_closes.iloc[-1])

                    valid_opens = s_data['Open'].dropna() if 'Open' in s_data.columns else pd.Series()
                    open_price = float(valid_opens.iloc[0]) if not valid_opens.empty else current_price
                    change_pct = ((current_price - open_price) / open_price * 100) if open_price else 0.0
                    
                    if np.isnan(current_price):
                        continue
                    if np.isnan(change_pct):
                        change_pct = 0.0

                    # Store by original symbol and sanitized symbol
                    results[s] = {"price": current_price, "day_change_pct": change_pct}
                    # Also map back to original symbols if they were missing .NS
                    for original in symbols:
                        if self._sanitize_symbol(original) == s:
                            results[original] = results[s]
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.error(f"Batch fetch error: {e}")
            return {}

INDIAN_STOCK_SECTORS = {
    # Energy / Oil & Gas
    "RELIANCE": "Energy",
    "ONGC": "Energy",
    "IOC": "Energy",
    "BPCL": "Energy",
    "HPCL": "Energy",
    "GAIL": "Energy",
    "OIL": "Energy",
    "PETRONET": "Energy",
    "COALINDIA": "Energy",

    # Technology / IT
    "TCS": "Technology",
    "INFY": "Technology",
    "WIPRO": "Technology",
    "HCLTECH": "Technology",
    "TECHM": "Technology",
    "LTIM": "Technology",
    "PERSISTENT": "Technology",
    "COFORGE": "Technology",
    "MPHASIS": "Technology",
    "KPITTECH": "Technology",
    "TATAELXSI": "Technology",
    "LTTS": "Technology",
    "OFSS": "Technology",

    # Financial Services / Banks / NBFC
    "HDFCBANK": "Financial Services",
    "ICICIBANK": "Financial Services",
    "SBIN": "Financial Services",
    "KOTAKBANK": "Financial Services",
    "AXISBANK": "Financial Services",
    "INDUSINDBK": "Financial Services",
    "BANKBARODA": "Financial Services",
    "PNB": "Financial Services",
    "CANBK": "Financial Services",
    "IDFCFIRSTB": "Financial Services",
    "BAJFINANCE": "Financial Services",
    "BAJAJFINSV": "Financial Services",
    "CHOLAFIN": "Financial Services",
    "PAYTM": "Financial Services",
    "HDFCLIFE": "Financial Services",
    "SBILIFE": "Financial Services",
    "ICICIPRULI": "Financial Services",
    "MUTHOOTFIN": "Financial Services",
    "SHRIRAMFIN": "Financial Services",
    "JIOFIN": "Financial Services",

    # Automobiles & Auto Components
    "TATAMOTORS": "Automobile",
    "MARUTI": "Automobile",
    "M&M": "Automobile",
    "BAJAJ-AUTO": "Automobile",
    "HEROMOTOCO": "Automobile",
    "EICHERMOT": "Automobile",
    "TVSMOTOR": "Automobile",
    "BHARATFORG": "Automobile",
    "BOSCHLTD": "Automobile",
    "MOTHERSON": "Automobile",
    "MRF": "Automobile",
    "BALKRISIND": "Automobile",

    # Consumer Defensive / FMCG
    "ITC": "Consumer Defensive",
    "HINDUNILVR": "Consumer Defensive",
    "NESTLEIND": "Consumer Defensive",
    "BRITANNIA": "Consumer Defensive",
    "TATACONSUM": "Consumer Defensive",
    "DABUR": "Consumer Defensive",
    "MARICO": "Consumer Defensive",
    "COLPAL": "Consumer Defensive",
    "GODREJCP": "Consumer Defensive",
    "VBL": "Consumer Defensive",

    # Consumer Cyclical / Retail / Consumer Durables
    "TITAN": "Consumer Cyclical",
    "TRENT": "Consumer Cyclical",
    "ASIANPAINT": "Consumer Cyclical",
    "BERGEPAINT": "Consumer Cyclical",
    "HAVELLS": "Consumer Cyclical",
    "DIXON": "Consumer Cyclical",
    "VOLTAS": "Consumer Cyclical",
    "PAGEIND": "Consumer Cyclical",
    "BATAINDIA": "Consumer Cyclical",
    "DMART": "Consumer Cyclical",
    "NYKAA": "Consumer Cyclical",
    "ZOMATO": "Consumer Cyclical",

    # Healthcare / Pharma
    "SUNPHARMA": "Healthcare",
    "CIPLA": "Healthcare",
    "DRREDDY": "Healthcare",
    "DIVISLAB": "Healthcare",
    "APOLLOHOSP": "Healthcare",
    "LUPIN": "Healthcare",
    "ZYDUSLIFE": "Healthcare",
    "TORNTPHARM": "Healthcare",
    "AUROPHARMA": "Healthcare",
    "BIOCON": "Healthcare",
    "MANKIND": "Healthcare",
    "MAXHEALTH": "Healthcare",

    # Industrials / Infrastructure / Capital Goods
    "LT": "Industrials",
    "SIEMENS": "Industrials",
    "ABB": "Industrials",
    "BEL": "Industrials",
    "HAL": "Industrials",
    "BHEL": "Industrials",
    "ADANIENT": "Industrials",
    "ADANIPORTS": "Industrials",
    "GMRINFRA": "Industrials",
    "CUMMINSIND": "Industrials",

    # Utilities / Power / Renewable
    "NTPC": "Utilities",
    "POWERGRID": "Utilities",
    "TATAPOWER": "Utilities",
    "ADANIGREEN": "Utilities",
    "ADANIPOWER": "Utilities",
    "NHPC": "Utilities",
    "SJVN": "Utilities",
    "SUZLON": "Utilities",
    "IREDA": "Utilities",

    # Basic Materials / Metals & Mining / Chemicals
    "TATASTEEL": "Basic Materials",
    "JSWSTEEL": "Basic Materials",
    "HINDALCO": "Basic Materials",
    "VEDL": "Basic Materials",
    "JINDALSTEL": "Basic Materials",
    "NMDC": "Basic Materials",
    "SAIL": "Basic Materials",
    "PIDILITIND": "Basic Materials",
    "SRF": "Basic Materials",
    "DEEPAKNTR": "Basic Materials",
    "TATACHEM": "Basic Materials",
    "ULTRACEMCO": "Basic Materials",
    "AMBUJACEM": "Basic Materials",
    "SHREECEM": "Basic Materials",
    "GRASIM": "Basic Materials",

    # Telecommunication
    "BHARTIARTL": "Communication Services",
    "IDEA": "Communication Services",
    "TATACOMM": "Communication Services",

    # Real Estate
    "DLF": "Real Estate",
    "GODREJPROP": "Real Estate",
    "LODHA": "Real Estate",
    "OBEROREALTY": "Real Estate",
    "PHOENIXLTD": "Real Estate",
}

    def _get_sector(self, symbol: str) -> str:
        """Fetches sector with fallback dictionary, caching, and yfinance."""
        if not symbol:
            return "Diversified"
            
        base_sym = str(symbol).strip().upper().split(".")[0]
        if base_sym in INDIAN_STOCK_SECTORS:
            return INDIAN_STOCK_SECTORS[base_sym]

        cache_key = make_key("stock_sector", base_sym)
        cached = get_cached(cache_key)
        if cached:
            return cached

        try:
            sanitized = self._sanitize_symbol(symbol)
            ticker = yf.Ticker(sanitized)
            info = ticker.info or {}
            sector = info.get("sector") or info.get("industry")
            if sector and str(sector).strip() and str(sector).lower() != "none":
                set_cached(cache_key, str(sector).strip(), SECTOR_TTL)
                return str(sector).strip()
        except Exception:
            pass

        return "Diversified"

    def _sanitize_symbol(self, symbol: str) -> str:
        if not symbol: return ""
        symbol = str(symbol).strip().upper()
        if "." not in symbol: return f"{symbol}.NS"
        return symbol

    def _sanitize_response(self, data):
        """Recursively replaces any NaN or Inf float values with 0.0 or safe defaults to ensure JSON compliance."""
        if isinstance(data, dict):
            return {k: self._sanitize_response(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_response(v) for v in data]
        elif isinstance(data, float):
            if np.isnan(data) or np.isinf(data):
                return 0.0
            return data
        return data


