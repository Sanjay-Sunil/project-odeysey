"""
URL routes for core app endpoints.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('agent', views.agent_endpoint, name='agent'),
    path('push', views.push_endpoint, name='push'),
    path('refer', views.refer_endpoint, name='refer'),
    path('heatmap-search', views.heatmap_search_endpoint, name='heatmap-search'),
]
