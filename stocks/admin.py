"""
stocks/admin.py
Register models with Django admin for easy data management.
"""

from django.contrib import admin
from stocks.models import PortfolioHolding, WatchlistItem


@admin.register(PortfolioHolding)
class PortfolioHoldingAdmin(admin.ModelAdmin):
    list_display = ["symbol", "quantity", "avg_buy_price", "invested_value", "created_at"]
    list_filter = ["sector"]
    search_fields = ["symbol"]
    ordering = ["symbol"]


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ["symbol", "user", "added_at"]
    search_fields = ["symbol"]
    ordering = ["-added_at"]
