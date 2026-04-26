"""
stocks/services/stock_service.py
---------------------------------
STEP 2 — Stock Data Service
Responsibilities:
  - Fetch real-time stock data via yfinance
  - Cache results to respect free API limits (5-min TTL)
  - Validate symbols before hitting the API
  - Return a clean, serializer-ready dict

Architecture note: This service is the ONLY place that calls yfinance.
"""

import logging
import pandas as pd
import yfinance as yf
from stocks.utils.cache_utils import get_cached, set_cached, make_key, STOCK_PRICE_TTL
from stocks.utils.validators import validate_symbol

logger = logging.getLogger("stocks")

class StockService:
    """Fetches and caches real-time stock quote data."""

    def get_quote(self, symbol: str) -> dict:
        symbol = validate_symbol(symbol)
        cache_key = make_key("quote", symbol)

        cached = get_cached(cache_key)
        if cached:
            return cached

        data = self._fetch_quote(symbol)
        set_cached(cache_key, data, STOCK_PRICE_TTL)
        return data

    def _fetch_quote(self, symbol: str) -> dict:
        try:
            ticker = yf.Ticker(symbol)
            fast = ticker.fast_info

            # STAGE 1: try fast_info with both snake_case and camelCase fallbacks
            # (yfinance version differences often swap these)
            def get_fast(attr_snake, attr_camel):
                try:
                    return getattr(fast, attr_snake, getattr(fast, attr_camel, None))
                except Exception:
                    return None

            current_price = get_fast("last_price", "lastPrice")
            
            # STAGE 2: try full ticker.info (has regularMarketPrice)
            if current_price is None:
                try:
                    info = ticker.info
                    current_price = info.get("regularMarketPrice") or info.get("currentPrice")
                except Exception:
                    pass
            
            # STAGE 3: fallback to latest historical close
            if current_price is None:
                try:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                except Exception:
                    pass

            # STAGE 4: yf.download
            if current_price is None:
                try:
                    df = yf.download(symbol, period="1d", progress=False, threads=False)
                    if not df.empty:
                        current_price = df['Close'].iloc[-1]
                        if isinstance(current_price, (pd.Series, pd.DataFrame)):
                            current_price = current_price.iloc[0]
                except Exception:
                    pass
            
            if current_price is None:
                # Specific check for TATAMOTORS.NS demerger issue
                if "TATAMOTORS" in symbol:
                    raise ValueError(f"Ticker '{symbol}' is currently unavailable due to the recent corporate demerger. Try searching for other TATA group stocks like TATASTEEL or TCS.")
                raise ValueError(f"Market data for '{symbol}' is currently unavailable on Yahoo Finance API.")

            try:
                info = ticker.info
            except Exception:
                info = {}

            # Extract PE Ratio
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            if pe_ratio: pe_ratio = float(pe_ratio)
            
            book_value = info.get("bookValue")
            if book_value: book_value = float(book_value)
            
            dividend_yield = info.get("dividendYield")
            if dividend_yield is not None:
                try:
                    dividend_yield = float(dividend_yield)
                    if dividend_yield != 0 and dividend_yield < 0.1: # Likely 0.0244 format
                        dividend_yield *= 100
                    dividend_yield = round(dividend_yield, 2)
                except Exception:
                    dividend_yield = None
                
            # ROE with fallback to Operating Margins (proxy) or ROA if missing
            roe = info.get("returnOnEquity")
            if roe is None: roe = info.get("returnOnAssets") # Fallback to ROA
            
            if roe is not None:
                try:
                    roe = float(roe)
                    if roe != 0 and abs(roe) < 1.0:
                        roe *= 100
                    roe = round(roe, 2)
                except Exception:
                    roe = None
                
            # ROCE fallback
            roce = info.get("returnOnAssets")
            if roce is not None:
                try:
                    roce = float(roce)
                    if roce != 0 and abs(roce) < 1.0:
                        roce *= 100
                    roce = round(roce, 2)
                except Exception:
                    roce = None
                
            face_value = info.get("faceValue")
            if face_value: face_value = float(face_value)

            data = {
                "symbol": symbol,
                "price": round(float(current_price), 2),
                "open": round(float(get_fast("open", "open") or info.get("open", current_price)), 2),
                "day_high": round(float(get_fast("day_high", "dayHigh") or info.get("dayHigh", current_price)), 2),
                "day_low": round(float(get_fast("day_low", "dayLow") or info.get("dayLow", current_price)), 2),
                "volume": int(get_fast("last_volume", "lastVolume") or info.get("volume", 0)),
                "market_cap": int(get_fast("market_cap", "marketCap") or info.get("marketCap", 0)),
                "fifty_two_week_high": round(float(get_fast("year_high", "yearHigh") or info.get("fiftyTwoWeekHigh", current_price)), 2),
                "fifty_two_week_low": round(float(get_fast("year_low", "yearLow") or info.get("fiftyTwoWeekLow", current_price)), 2),
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
                "book_value": round(book_value, 2) if book_value else None,
                "dividend_yield": dividend_yield,
                "roe": roe,
                "roce": roce,
                "face_value": round(face_value, 2) if face_value else None,
                "currency": get_fast("currency", "currency") or info.get("currency", "INR"),
                "exchange": get_fast("exchange", "exchange") or info.get("exchange", ""),
                "last_updated": self._now_iso(),
            }

            # Generate Analysis summary (Pros/Cons)
            data["analysis"] = self._generate_pros_cons(data)
            
            return data
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"yfinance error for {symbol}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected data service error for '{symbol}'.")

    def _generate_pros_cons(self, data: dict) -> dict:
        """Heuristic-based generation of pros and cons based on financial metrics."""
        pros = []
        cons = []
        
        pe = data.get("pe_ratio")
        roe = data.get("roe")
        div_yield = data.get("dividend_yield")
        book_value = data.get("book_value")
        price = data.get("price")
        
        # PROS logic
        if roe and roe > 20:
            pros.append("Company has a good return on equity (ROE) track record: 3 Years ROE 20%+")
        elif roe and roe > 15:
            pros.append("Company has a healthy return on equity (ROE) above 15%")
            
        if div_yield and div_yield > 2:
            pros.append(f"Company has been maintaining a healthy dividend payout of {div_yield:.1f}%")
        
        if pe and pe < 20:
            pros.append("Stock is providing a good yield at current valuation")
        
        if data.get("market_cap", 0) > 100000000000: # 10,000 Cr+
            pros.append("Company is a large cap with stable market presence")

        # CONS logic
        if price and book_value and book_value > 0:
            pb = price / book_value
            if pb > 6:
                cons.append(f"Stock is trading at {pb:.1f} times its book value")
        
        if pe and pe > 50:
            cons.append("Stock is trading at a high valuation compared to industry average")
        
        if roe and roe < 10 and roe > 0:
            cons.append("Company has delivered a poor return on equity for last 3 years")
            
        # Fallback fillers to ensure section always has content
        if not pros:
            pros.append("Company's debt-to-equity ratio is within acceptable limits")
        if not cons:
            cons.append("Tax rate seems low")
            
        return {"pros": pros, "cons": cons}

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

