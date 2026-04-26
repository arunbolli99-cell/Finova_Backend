"""
stocks/views/stock_views.py — STEP 2
GET /api/stock/<symbol>/
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.stock_service import StockService

_service = StockService()


class StockQuoteView(APIView):
    """Returns current quote for a stock symbol."""

    def get(self, request, symbol: str):
        try:
            data = _service.get_quote(symbol)
            return Response({"success": True, "data": data})
        except ValueError as e:
            # Return 200 even on known errors to avoid "scary" red console errors for users
            return Response({"success": False, "error": str(e)}, status=200)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=503)
