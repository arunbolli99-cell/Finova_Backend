"""
stocks/services/sentiment_service.py
--------------------------------------
STEP 4 (Part B) — VADER Sentiment Scoring
Why VADER?
  - Purpose-built for social media / news text
  - No API needed (runs locally)
  - Fast and handles finance jargon well
  - Compound score: -1 (most negative) to +1 (most positive)

Architecture: SentimentService enriches the raw article dicts
from NewsService, then returns them. Clear single responsibility.
"""

import logging
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

logger = logging.getLogger("stocks")

# Download VADER lexicon on first use (cached locally after first download)
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    logger.info("Downloading VADER lexicon...")
    nltk.download("vader_lexicon", quiet=True)


class SentimentService:
    """Enriches news articles with VADER sentiment scores."""

    def __init__(self):
        self._analyzer = SentimentIntensityAnalyzer()

    def analyze_articles(self, articles: list[dict]) -> list[dict]:
        """
        Add sentiment data to each article dict.
        Returns articles sorted by published_at (newest first).
        """
        enriched = []
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '') or ''}"
            scores = self._analyzer.polarity_scores(text.strip())
            compound = round(scores["compound"], 4)

            article["sentiment"] = self._label(compound)
            article["sentiment_score"] = compound
            article["sentiment_detail"] = {
                "positive": round(scores["pos"], 3),
                "negative": round(scores["neg"], 3),
                "neutral": round(scores["neu"], 3),
            }
            enriched.append(article)

        return enriched

    def aggregate_sentiment(self, articles: list[dict]) -> dict:
        """
        Compute an overall sentiment summary across all articles.
        Used by the recommendation engine.
        """
        if not articles:
            return {"label": "Neutral", "score": 0.0, "article_count": 0, "confidence": 0.0}

        scores = [a.get("sentiment_score", 0) for a in articles]
        avg = sum(scores) / len(scores)
        
        # Simple confidence: higher when more articles agree or have strong sentiment
        pos = sum(1 for s in scores if s > 0.05)
        neg = sum(1 for s in scores if s < -0.05)
        total = len(articles)
        
        # Confidence is higher if majority agree
        agreement = max(pos, neg) / total if total > 0 else 0
        confidence = round(0.5 + (agreement * 0.5), 2) # Base 50% + up to 50% more

        return {
            "label": self._label(avg),
            "score": round(avg, 4),
            "article_count": len(articles),
            "positive_count": pos,
            "negative_count": neg,
            "neutral_count": total - pos - neg,
            "confidence": confidence,
        }

    @staticmethod
    def _label(compound: float) -> str:
        if compound >= 0.05:
            return "Positive"
        if compound <= -0.05:
            return "Negative"
        return "Neutral"
