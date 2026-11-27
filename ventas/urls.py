from django.urls import path
from .views import VentaDetailView, VentaListCreateView

urlpatterns = [
    path("", VentaListCreateView.as_view(), name="venta-list-create"),
    path("<uuid:pk>/", VentaDetailView.as_view(), name="venta-detail"),
]