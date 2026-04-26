from rest_framework import views, status, permissions
from rest_framework.response import Response
from stocks.models import PortfolioHolding, WatchlistItem

class PortfolioHoldingView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        holdings = PortfolioHolding.objects.filter(user=request.user)
        data = [
            {
                "id": h.id,
                "symbol": h.symbol,
                "quantity": float(h.quantity),
                "avg_buy_price": float(h.avg_buy_price),
                "purchase_date": h.purchase_date.isoformat() if h.purchase_date else None,
                "created_at": h.created_at.isoformat()
           } for h in holdings
        ]
        return Response({"holdings": data})

    def post(self, request):
        from stocks.utils.validators import validate_symbol, validate_positive_number
        
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
            
        holding, created = PortfolioHolding.objects.get_or_create(
            user=request.user, 
            symbol=symbol,
            defaults={
                'quantity': quantity, 
                'avg_buy_price': avg_buy_price,
                'purchase_date': purchase_date
            }
        )
        
        if not created:
            holding.quantity = quantity
            holding.avg_buy_price = avg_buy_price
            if purchase_date:
                holding.purchase_date = purchase_date
            holding.save()
            
        return Response({'success': True, 'message': 'Portfolio updated'})

    def delete(self, request):
        symbol = request.data.get('symbol')
        if not symbol:
             return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
        PortfolioHolding.objects.filter(user=request.user, symbol=symbol).delete()
        return Response({'success': True})


class WatchlistView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = WatchlistItem.objects.filter(user=request.user)
        data = [
            {
                "id": w.id,
                "symbol": w.symbol,
            } for w in items
        ]
        return Response({"watchlist": data})

    def post(self, request):
        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        WatchlistItem.objects.get_or_create(user=request.user, symbol=symbol)
        return Response({'success': True})

    def delete(self, request):
        symbol = request.data.get('symbol')
        if not symbol:
            return Response({'error': 'Symbol is required'}, status=status.HTTP_400_BAD_REQUEST)
        WatchlistItem.objects.filter(user=request.user, symbol=symbol).delete()
        return Response({'success': True})
