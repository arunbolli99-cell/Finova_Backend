"""
stocks/utils/validators.py
---------------------------
Input validation utilities — Indian market edition.
Supported exchanges: NSE (.NS) and BSE (.BO).
Plain symbols like "RELIANCE" are auto-normalized to "RELIANCE.NS".
"""

import re
import logging

logger = logging.getLogger("stocks")

# Index symbols allowed without suffix (Nifty, Sensex, etc.)
INDEX_SYMBOLS = {
    "^NSEI",    # Nifty 50
    "^BSESN",   # Sensex
    "^NSEBANK", # Bank Nifty
    "^CNXIT",   # Nifty IT
    "^CNXAUTO", # Nifty Auto
    "^CNXPHARMA", # Nifty Pharma
    "^CNXMETAL", # Nifty Metal
    "^CNXINFRA", # Nifty Infra
}

# Base symbol: 1-20 uppercase letters/digits
BASE_SYMBOL_REGEX = re.compile(r"^[A-Z0-9&\-]{1,20}$")

# Allowed Indian exchange suffixes
INDIAN_SUFFIXES = {".NS", ".BO"}

VALID_PERIODS = {"7d", "30d", "60d", "90d", "1y", "2y", "5y"}


def validate_symbol(symbol: str) -> str:
    """
    Normalize and validate an Indian stock ticker symbol.

    Rules:
      - "RELIANCE"      → "RELIANCE.NS"   (default NSE)
      - "RELIANCE.NS"   → "RELIANCE.NS"   (NSE — kept)
      - "RELIANCE.BO"   → "RELIANCE.BO"   (BSE — kept)
      - "^NSEI"         → "^NSEI"         (index — kept)
      - "AAPL"          → ValueError      (no .NS/.BO suffix after normalizing)

    Returns cleaned symbol or raises ValueError.
    """
    if not symbol:
        raise ValueError("Stock symbol is required.")

    cleaned = symbol.strip().upper()

    # Allow index symbols directly
    if cleaned in INDEX_SYMBOLS:
        return cleaned

    # If already has a suffix — validate it's a supported Indian exchange
    if "." in cleaned:
        parts = cleaned.rsplit(".", 1)
        suffix = f".{parts[1]}"
        if suffix not in INDIAN_SUFFIXES:
            raise ValueError(
                f"Only Indian exchanges are supported. "
                f"Use NSE (e.g. RELIANCE.NS) or BSE (e.g. RELIANCE.BO). "
                f"Got suffix '{suffix}'."
            )
        base = parts[0]
        if not BASE_SYMBOL_REGEX.match(base):
            raise ValueError(f"Invalid symbol base '{base}'.")
        return cleaned

    # No suffix — auto-append NSE
    if not BASE_SYMBOL_REGEX.match(cleaned):
        raise ValueError(
            f"Invalid symbol '{cleaned}'. Use uppercase letters/digits "
            f"(e.g. RELIANCE, TCS, INFY)."
        )
    normalized = f"{cleaned}.NS"
    logger.debug(f"Symbol auto-normalized: {symbol} → {normalized}")
    return normalized


def validate_period(period: str) -> str:
    """Validate historical data period parameter."""
    if period not in VALID_PERIODS:
        raise ValueError(
            f"Invalid period '{period}'. Choose from: {', '.join(sorted(VALID_PERIODS))}"
        )
    return period


def validate_positive_number(value, name: str = "value") -> float:
    """Ensure a value is a positive number."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{name}' must be a number.")
    if num <= 0:
        raise ValueError(f"'{name}' must be positive.")
    return num

