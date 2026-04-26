"""
stocks/views/history_views.py — STEP 3
GET /api/history/<symbol>/?period=30d
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.history_service import HistoryService

_service = HistoryService()


class HistoryView(APIView):
    """Returns OHLCV + technical indicators for a symbol."""

    def get(self, request, symbol: str):
        try:
            period = request.query_params.get("period", "30d")
            data = _service.get_history(symbol, period)
            return Response({"success": True, "data": data})
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)
        except Exception as e:
            return Response({"success": False, "error": "Internal technical error fetching history."}, status=503)
