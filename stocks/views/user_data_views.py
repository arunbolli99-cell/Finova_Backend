from rest_framework import views, status, permissions
from rest_framework.response import Response
from stocks.models import PortfolioHolding, WatchlistItem

class PortfolioHoldingView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"holdings": []})
            
        from stocks.services.portfolio_service import PortfolioService
        service = PortfolioService()

        holdings = PortfolioHolding.objects.filter(user=request.user)
        data = []
        for h in holdings:
            sec = h.sector or service._get_sector(h.symbol)
            if not h.sector and sec:
                h.sector = sec
                h.save(update_fields=['sector'])
            data.append({
                "id": h.id,
                "symbol": h.symbol,
                "quantity": float(h.quantity),
                "avg_buy_price": float(h.avg_buy_price),
                "sector": sec,
                "purchase_date": h.purchase_date.isoformat() if hasattr(h.purchase_date, 'isoformat') else (str(h.purchase_date) if h.purchase_date else None),
                "created_at": h.created_at.isoformat() if hasattr(h.created_at, 'isoformat') else str(h.created_at)
            })
        return Response({"holdings": data})

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        from stocks.utils.validators import validate_symbol, validate_positive_number
        from stocks.services.portfolio_service import PortfolioService
        
        symbol_raw = request.data.get('symbol')
        quantity_raw = request.data.get('quantity')
        avg_buy_price_raw = request.data.get('avg_buy_price')
        purchase_date = request.data.get('purchase_date')
        
        if not symbol_raw or quantity_raw is None or avg_buy_price_raw is None:
            return Response({'error': 'Missing fields'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            symbol = validate_symbol(symbol_raw)
            quantity = validate_positive_number(quantity_raw, "quantity")
            avg_buy_price = validate_positive_number(avg_buy_price_raw, "avg_buy_price")
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        service = PortfolioService()
        sector = service._get_sector(symbol)
            
        holding, created = PortfolioHolding.objects.get_or_create(
            user=request.user, 
            symbol=symbol,
            defaults={
                'quantity': quantity, 
                'avg_buy_price': avg_buy_price,
                'sector': sector,
                'purchase_date': purchase_date
            }
        )
        
        if not created:
            holding.quantity = quantity
            holding.avg_buy_price = avg_buy_price
            holding.sector = sector
            if purchase_date:
                holding.purchase_date = purchase_date
            holding.save()
            
        return Response({'success': True, 'message': 'Portfolio updated', 'holding': {
            'id': holding.id,
            'symbol': holding.symbol,
            'quantity': float(holding.quantity),
            'avg_buy_price': float(holding.avg_buy_price),
            'sector': holding.sector,
            'purchase_date': holding.purchase_date.isoformat() if hasattr(holding.purchase_date, 'isoformat') else (str(holding.purchase_date) if holding.purchase_date else None)
        }})

    def delete(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        symbol = request.data.get('symbol')
        if not symbol:
             return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
        PortfolioHolding.objects.filter(user=request.user, symbol=symbol).delete()
        return Response({'success': True})


class WatchlistView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"watchlist": []})

        items = WatchlistItem.objects.filter(user=request.user)
        data = [
            {
                "id": w.id,
                "symbol": w.symbol,
            } for w in items
        ]
        return Response({"watchlist": data})

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        WatchlistItem.objects.get_or_create(user=request.user, symbol=symbol)
        return Response({'success': True})

    def delete(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
        WatchlistItem.objects.filter(user=request.user, symbol=symbol).delete()
        return Response({'success': True})
