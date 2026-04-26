"""
stocks/views/analysis_views.py
------------------------------
Views for deep historical analysis.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.analysis_service import HistoryAnalysisService

_analysis_service = HistoryAnalysisService()

class HistoryAnalysisView(APIView):
    """Returns full history and investor metadata for a stock."""

    def get(self, request, symbol: str):
        try:
            data = _analysis_service.get_history_analysis(symbol)
            return Response({
                "success": True, 
                "data": data
            })
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=400)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=503)
