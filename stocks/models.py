"""
stocks/models.py
-----------------
Django ORM models for persistent data.

PortfolioHolding: Stores user stock positions in SQL Server.
CachedStockData: Optional DB-level cache for expensive computations.

Architecture note: We use Django's built-in ORM — no raw SQL.
mssql-django translates these models to T-SQL automatically.
"""

from django.db import models
from django.contrib.auth.models import User


class PortfolioHolding(models.Model):
    """A single stock position in a user's portfolio."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="holdings",
        null=True,   # Allow anonymous for demo
        blank=True,
    )
    symbol = models.CharField(max_length=20, db_index=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    avg_buy_price = models.DecimalField(max_digits=15, decimal_places=4)
    sector = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Portfolio Holding"
        verbose_name_plural = "Portfolio Holdings"
        ordering = ["symbol"]
        unique_together = [("user", "symbol")]

    def __str__(self):
        return f"{self.symbol} × {self.quantity} @ {self.avg_buy_price}"

    @property
    def invested_value(self):
        return float(self.quantity) * float(self.avg_buy_price)


class WatchlistItem(models.Model):
    """Symbols a user is tracking but hasn't invested in."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="watchlist",
        null=True,
        blank=True,
    )
    symbol = models.CharField(max_length=20, db_index=True)
    notes = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Watchlist Item"
        ordering = ["-added_at"]
        unique_together = [("user", "symbol")]

    def __str__(self):
        return f"Watch: {self.symbol}"

class UserProfile(models.Model):
    """Extended user profile data with personal details."""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='N')
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    profile_pic_base64 = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"
