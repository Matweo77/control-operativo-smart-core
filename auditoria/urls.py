from django.urls import path
from .views import MovimientoInventarioListView

urlpatterns = [
    path("", MovimientoInventarioListView.as_view(), name="auditoria-lista"),
    path(
        "movimientos/",
        MovimientoInventarioListView.as_view(),
        name="auditoria-movimientos",
    ),
]