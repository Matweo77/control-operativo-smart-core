from django.urls import path
from .views import (
    EmpresaDetalleView,
    PerfilUsuarioDetailView,
    PerfilUsuarioListCreateView,
    SucursalListView,
)

urlpatterns = [
    path("empresa/", EmpresaDetalleView.as_view(), name="organizacion-empresa"),
    path("sucursales/", SucursalListView.as_view(), name="organizacion-sucursales"),
    path(
        "usuarios/",
        PerfilUsuarioListCreateView.as_view(),
        name="organizacion-usuarios",
    ),
    path(
        "usuarios/<uuid:pk>/",
        PerfilUsuarioDetailView.as_view(),
        name="organizacion-usuario-detail",
    ),
]