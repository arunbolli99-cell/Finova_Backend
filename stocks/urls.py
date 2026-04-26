
from django.urls import path
from stocks.views.stock_views import StockQuoteView
from stocks.views.history_views import HistoryView
from stocks.views.news_views import NewsView
from stocks.views.backtest_views import BacktestView
from stocks.views.portfolio_views import PortfolioAnalyseView
from stocks.views.analysis_views import HistoryAnalysisView
from stocks.views.auth_views import SignupView, LoginView, UserContextView, UserProfileView
from stocks.views.user_data_views import PortfolioHoldingView, WatchlistView

urlpatterns = [
    # Stock data
    path("stock/<str:symbol>/", StockQuoteView.as_view(), name="stock-quote"),
    path("history/<str:symbol>/", HistoryView.as_view(), name="stock-history"),

    # News & sentiment
    path("news/<str:symbol>/", NewsView.as_view(), name="stock-news"),

    # Auth & User Data
    path("auth/register/", SignupView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", UserContextView.as_view(), name="auth-me"),
    path("auth/profile/", UserProfileView.as_view(), name="auth-profile"),
    
    path("portfolio/holdings/", PortfolioHoldingView.as_view(), name="portfolio-holdings"),
    path("watchlist/", WatchlistView.as_view(), name="watchlist-items"),

    # Advanced features
    path("backtest/", BacktestView.as_view(), name="backtest"),
    path("portfolio/analyse/", PortfolioAnalyseView.as_view(), name="portfolio-analyse"),
    path("analysis/history/<str:symbol>/", HistoryAnalysisView.as_view(), name="history-analysis"),
]
