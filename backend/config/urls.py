"""
URL configuration for Rare Disease Federated Detection MVP.
"""
from django.urls import path, include

urlpatterns = [
    path('', include('core.urls')),
]
