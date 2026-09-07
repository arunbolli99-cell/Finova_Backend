"""
stocks/views/news_views.py — STEP 4
GET /api/news/<symbol>/?company=Apple Inc
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.news_service import NewsService
from stocks.services.sentiment_service import SentimentService
from rest_framework.permissions import AllowAny

_news_svc = NewsService()
_sentiment_svc = SentimentService()


class NewsView(APIView):
    """Returns sentiment-enriched news articles for a stock."""
    permission_classes = [AllowAny]

    def get(self, request, symbol: str):
        try:
            company = request.query_params.get("company", "")
            articles = _news_svc.get_news(symbol, company)
            enriched = _sentiment_svc.analyze_articles(articles)
            aggregate = _sentiment_svc.aggregate_sentiment(enriched)

            return Response({
                "success": True,
                "data": {
                    "articles": enriched,
                    "aggregate_sentiment": aggregate,
                },
            })
        except Exception as e:
            return Response({
                "success": True,
                "data": {
                    "articles": _news_svc._get_curated_fallback_news(symbol, ""),
                    "aggregate_sentiment": {"label": "Neutral", "score": 0.0, "article_count": 0, "confidence": 0.5},
                },
            })

