"""
stocks/utils/exception_handler.py
-----------------------------------
Custom DRF exception handler.
Wraps all errors in a consistent JSON envelope:

  {
    "success": false,
    "error": "Human-readable message",
    "code": "HTTP_404_NOT_FOUND"
  }
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger("stocks")


def custom_exception_handler(exc, context):
    """Override DRF's default handler for consistent error responses."""
    # Let DRF handle it first
    response = exception_handler(exc, context)

    if response is not None:
        logger.warning(
            f"API error [{response.status_code}] on "
            f"{context['request'].path}: {exc}"
        )
        response.data = {
            "success": False,
            "error": _extract_message(response.data),
            "code": response.status_code,
        }
    else:
        # Unhandled exception — return 500
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        response = Response(
            {
                "success": False,
                "error": "An unexpected server error occurred.",
                "code": 500,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _extract_message(data) -> str:
    """Flatten DRF's error dict/list into a single string."""
    if isinstance(data, dict):
        messages = []
        for key, val in data.items():
            if isinstance(val, list):
                messages.extend(val)
            else:
                messages.append(str(val))
        return " | ".join(str(m) for m in messages)
    if isinstance(data, list):
        return " | ".join(str(m) for m in data)
    return str(data)
