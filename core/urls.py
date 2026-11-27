from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/catalogo/", include("catalogo.urls")),
    path("api/clientes/", include("clientes.urls")),
    path("api/ventas/", include("ventas.urls")),
]