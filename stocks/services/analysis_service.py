"""
stocks/services/analysis_service.py
-----------------------------------
Service for performing deep historical and investor research.
"""

import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone
from stocks.utils.cache_utils import get_cached, set_cached, make_key, HISTORY_TTL
from stocks.utils.validators import validate_symbol

logger = logging.getLogger("stocks")

class HistoryAnalysisService:
    """Provides deep historical performance and company metadata analysis."""

    def get_history_analysis(self, symbol: str) -> dict:
        symbol = validate_symbol(symbol)
        cache_key = make_key("history_analysis", symbol)
        
        cached = get_cached(cache_key)
        if cached:
            return cached
            
        result = self._fetch_and_analyze(symbol)
        set_cached(cache_key, result, HISTORY_TTL) # Use same TTL as other heavy data
        return result

    def _clean_historical_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detects the 'Real' listing day by searching for a massive volume spike (> 100x)
        in the first few years. This removes inherited/backfilled data (TCS) 
        while preserving legitimate early history (Wipro).
        """
        if df.empty: return df
        
        # A. Start from the first day with any activity
        first_nonzero = df[df['Volume'] > 0].index
        if first_nonzero.empty: return df
        df = df.loc[first_nonzero[0]:]
        
        # B. Detect 'Listing Event' Spike
        # IPOs on Yahoo usually show a massive jump compared to pre-listing 'dummy' data.
        # We only check the first 5 years of available data.
        check_limit = df.index[0] + pd.Timedelta(days=5*365)
        early_df = df[df.index <= check_limit]
        
        if len(early_df) < 30: return df
        
        max_v = df['Volume'].max()
        rolling_vol = early_df['Volume'].rolling(window=20).mean()
        
        for i in range(20, len(early_df)):
            current_v = early_df['Volume'].iloc[i]
            avg_v = rolling_vol.iloc[i-1]
            
            # Massive jump (> 100x) AND Significant absolute volume (> 5% of peak)
            if avg_v > 0 and (current_v / avg_v) > 100 and (current_v > 0.05 * max_v):
                # Found the likely IPO/Listing day!
                return df.loc[early_df.index[i]:]
        
        return df

    def _fetch_and_analyze(self, symbol: str) -> dict:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 1. Fetch Max History
            df = ticker.history(period="max", auto_adjust=False)
            if df.empty:
                raise ValueError(f"No historical data available for {symbol}")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 2. Clean 'Dirty' History (Remove pre-listing junk like CMC data in TCS)
            df = self._clean_historical_data(df)

            # 3. Resample to Financial Year-End (March)
            try:
                annual_data = df[['Close', 'Adj Close']].resample('YE-MAR').last()
            except:
                try:
                    annual_data = df[['Close', 'Adj Close']].resample('A-MAR').last()
                except:
                    annual_data = df[['Close', 'Adj Close']].resample('YE').last()
                
            yearly_returns = annual_data['Adj Close'].pct_change().dropna()
            
            now = datetime.now()
            current_fy_end_year = now.year if now.month <= 3 else now.year + 1

            returns_data = []
            for date in annual_data.index:
                if date not in yearly_returns.index and date != annual_data.index[0]:
                    continue
                
                if date.year == current_fy_end_year:
                    year_label = f"FY {date.year-1}-Present"
                else:
                    year_label = f"FY {date.year-1}-{str(date.year)[2:]}"

                returns_data.append({
                    "year": year_label,
                    "year_val": int(date.year), # keep for sorting
                    "close": float(round(annual_data.loc[date, 'Close'], 2)),
                    "return_pct": float(round(yearly_returns.get(date, 0) * 100, 2))
                })
            
            # Ensure the first year has 0 return if it's the start
            if returns_data:
                returns_data[0]["return_pct"] = 0.0

            # 3. Extract Key Investor Details
            return {
                "symbol": symbol,
                "profile": {
                    "name": info.get("longName") or info.get("shortName") or symbol,
                    "sector": info.get("sector", "N/A"),
                    "industry": info.get("industry", "N/A"),
                    "website": info.get("website", "N/A"),
                    "summary": info.get("longBusinessSummary", "No business summary available."),
                    "currency": info.get("currency", "INR"),
                    "exchange": info.get("exchange", "N/A"),
                },
                "stats": {
                    "market_cap": info.get("marketCap"),
                    "trailing_pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "price_to_book": info.get("priceToBook"),
                    "dividend_yield": info.get("dividendYield", 0) * 100 if isinstance(info.get("dividendYield"), (int, float)) else 0,
                    "beta": info.get("beta"),
                    "eps_trailing": info.get("trailingEps"),
                    "revenue_growth": info.get("revenueGrowth", 0) * 100 if isinstance(info.get("revenueGrowth"), (int, float)) else 0,
                },
                "yearly_performance": sorted(returns_data, key=lambda x: x['year_val'], reverse=True),
                "total_years_listed": len(returns_data),
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"History analysis failed for {symbol}: {e}")
            raise RuntimeError(f"Could not perform deep history analysis for {symbol}")
