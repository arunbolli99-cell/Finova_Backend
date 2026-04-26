"""
stocks/utils/cache_utils.py
----------------------------
Thin wrapper around Django's cache framework.
Architecture decision: All services call these helpers so we can swap
the cache backend (local-mem → Redis) in settings.py without touching
any service code.
"""

import logging
import numpy as np
from django.core.cache import cache

logger = logging.getLogger("stocks")

# Default TTLs
STOCK_PRICE_TTL = 300        # 5 min — prices change frequently
HISTORY_TTL = 3600           # 1 hour — historical data is stable
NEWS_TTL = 900               # 15 min — news refreshes moderately
PREDICTION_TTL = 1800        # 30 min — ML predictions are expensive


def make_key(prefix: str, *parts) -> str:
    """Build a namespaced, sanitized cache key."""
    key = f"finova:{prefix}:" + ":".join(str(p) for p in parts)
    return key.replace(" ", "_").lower()


def get_cached(key: str):
    """Retrieve a cached value. Returns None on miss."""
    value = cache.get(key)
    if value is not None:
        logger.debug(f"Cache HIT  → {key}")
    else:
        logger.debug(f"Cache MISS → {key}")
    return value


def sanitize_data(data):
    """Recursively replace NaN and inf values with None for JSON compliance."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, float):
        if np.isnan(data) or np.isinf(data):
            return None
    return data


def set_cached(key: str, value, ttl: int = STOCK_PRICE_TTL) -> None:
    """Store a value in cache with a TTL. Sanitizes for JSON compliance."""
    sanitized_value = sanitize_data(value)
    cache.set(key, sanitized_value, ttl)
    logger.debug(f"Cache SET  → {key} (TTL={ttl}s)")


def invalidate(key: str) -> None:
    """Explicitly evict a cache entry."""
    cache.delete(key)
    logger.info(f"Cache EVICTED → {key}")
