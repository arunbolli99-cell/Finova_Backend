"""
stocks/services/news_service.py
---------------------------------
STEP 4 (Part A) — News Fetching Service
Fetches stock-related news from NewsAPI.
Architecture: Thin wrapper that adds caching over NewsAPI.
The actual sentiment scoring is delegated to SentimentService.
"""

import logging
from datetime import datetime, timedelta
from django.conf import settings
from newsapi import NewsApiClient
from stocks.utils.cache_utils import get_cached, set_cached, make_key, NEWS_TTL
from stocks.utils.validators import validate_symbol

logger = logging.getLogger("stocks")

MAX_ARTICLES = 50


class NewsService:
    """Fetches recent news headlines for a given stock ticker."""

    def __init__(self):
        self._api_key = settings.NEWS_API_KEY
        if not self._api_key:
            logger.warning("NEWS_API_KEY not set. News endpoint will return mock results.")
            self.newsapi = None
        else:
            self.newsapi = NewsApiClient(api_key=self._api_key)

    def get_news(self, symbol: str, company_name: str = "") -> list[dict]:
        """
        Fetch up to MAX_ARTICLES articles for the symbol.
        Falls back to empty list if API key is missing.
        """
        if symbol.upper() == "GENERAL":
            symbol = "GENERAL"
        else:
            symbol = validate_symbol(symbol)
        
        cache_key = make_key("news", symbol)

        cached = get_cached(cache_key)
        if cached: # Return cached only if it has articles
            return cached

        articles = self._fetch_articles(symbol, company_name)
        set_cached(cache_key, articles, NEWS_TTL)
        return articles

    def _fetch_articles(self, symbol: str, company_name: str) -> list[dict]:
        if not self.newsapi:
            return self._get_mock_news(symbol, company_name)

        # Strip exchange suffix for cleaner queries (.NS / .BO)
        base_symbol = symbol.rsplit(".", 1)[0] if "." in symbol else symbol

        # Strategy: try queries from most-specific to broadest
        queries = []
        if symbol.upper() == "GENERAL":
            queries = ["Indian stock market", "Nifty Sensex"]
        else:
            if company_name:
                queries.append(company_name)
            queries.append(base_symbol)

        articles = []
        five_days_ago = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        for query in queries:
            try:
                response = self.newsapi.get_everything(
                    q=query,
                    language='en',
                    sort_by='publishedAt',
                    from_param=five_days_ago,
                    page_size=MAX_ARTICLES
                )
                
                raw_articles = response.get("articles", [])
                if raw_articles:
                    logger.info(f"NewsAPI found {len(raw_articles)} articles for '{query}'")
                    articles = raw_articles
                    break
            except Exception as e:
                logger.error(f"NewsAPI error for query '{query}': {e}")
                continue
        
        if not articles:
            logger.info("Providing mock news articles as fallback.")
            articles = self._get_mock_news(symbol, company_name)

        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
                "image_url": a.get("urlToImage", ""),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

    def _get_mock_news(self, symbol: str, company_name: str) -> list[dict]:
        """Returns sample articles when API is unavailable or rate-limited."""
        if symbol.upper() == "GENERAL":
            return [
                {
                    "title": "Nifty 50 and Sensex Hit Record Highs Amid Global Rally",
                    "description": "Indian benchmark indices touched new peaks today as strong domestic flows and positive global cues boosted investor sentiment across sectors.",
                    "url": "https://economictimes.indiatimes.com/markets/stocks/news",
                    "source": {"name": "Finova Daily"},
                    "publishedAt": datetime.now().isoformat(),
                    "urlToImage": ""
                },
                {
                    "title": "RBI Keeps Repo Rate Unchanged, Maintains 'Withdrawal of Accommodation' Stance",
                    "description": "The Reserve Bank of India's Monetary Policy Committee decided to keep the policy repo rate unchanged at 6.50% for the seventh consecutive time.",
                    "url": "https://www.livemint.com/economy",
                    "source": {"name": "Economic Times (Mock)"},
                    "publishedAt": datetime.now().isoformat(),
                    "urlToImage": ""
                },
                {
                    "title": "FIIs Turn Net Buyers in Indian Equities After Brief Pause",
                    "description": "Foreign Institutional Investors (FIIs) have returned to the Indian markets, pumping in over ₹2,500 crore in the last two trading sessions.",
                    "url": "https://www.moneycontrol.com/news/business/markets/",
                    "source": {"name": "Moneycontrol (Mock)"},
                    "publishedAt": datetime.now().isoformat(),
                    "urlToImage": ""
                }
            ]
        
        display_name = company_name or symbol
        return [
            {
                "title": f"{display_name} Reports Strong Q3 Results, Beats Street Estimates",
                "description": f"{display_name} has announced its third-quarter financial results, showcasing significant growth in revenue and net profit margins.",
                "url": "https://www.financialexpress.com/market/",
                "source": {"name": "Financial Express (Mock)"},
                "publishedAt": datetime.now().isoformat(),
                "urlToImage": ""
            },
            {
                "title": f"Market Analysts Bullish on {display_name} Long-term Prospects",
                "description": f"Several brokerage firms have maintained their 'Buy' rating on {display_name}, citing strong order books and expansion plans.",
                "url": "https://www.business-standard.com/markets",
                "source": {"name": "Mint (Mock)"},
                "publishedAt": datetime.now().isoformat(),
                "urlToImage": ""
            }
        ]

