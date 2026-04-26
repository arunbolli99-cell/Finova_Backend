"""
Finova — Root URL Configuration
All API endpoints are prefixed with /api/
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("stocks.urls")),
]
