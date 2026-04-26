"""
stocks/views/backtest_views.py — STEP 8
POST /api/backtest/
Body: {"symbol": "AAPL", "initial_investment": 10000, "period": "2y"}
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.services.backtest_service import BacktestService

_service = BacktestService()


class BacktestView(APIView):
    """Runs MA crossover backtesting for a given symbol and investment."""

    def post(self, request):
        body = request.data
        symbol = body.get("symbol", "")
        initial_investment = float(body.get("initial_investment", 10000))
        period = body.get("period", "2y")
        short_window = int(body.get("short_window", 20))
        long_window = int(body.get("long_window", 50))

        data = _service.run(
            symbol=symbol,
            initial_investment=initial_investment,
            period=period,
            short_window=short_window,
            long_window=long_window,
        )
        return Response({"success": True, "data": data})
