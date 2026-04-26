"""
stocks/views/portfolio_views.py — STEP 9
POST /api/portfolio/analyse/
Body: {"holdings": [{"symbol": "AAPL", "quantity": 10, "avg_buy_price": 150}, ...]}
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.portfolio_service import PortfolioService

_service = PortfolioService()


class PortfolioAnalyseView(APIView):
    """Analyses a basket of holdings for P&L and diversification."""

    def post(self, request):
        holdings = request.data.get("holdings", [])
        if not isinstance(holdings, list):
            return Response(
                {"success": False, "error": "'holdings' must be a list."},
                status=400,
            )
        try:
            data = _service.analyse(holdings)
            return Response({"success": True, "data": data})
        except ValueError as e:
            return Response(
                {"success": False, "error": str(e)},
                status=400,
            )
        except Exception as e:
            return Response(
                {"success": False, "error": f"An unexpected error occurred during analysis: {str(e)}"},
                status=500,
            )
