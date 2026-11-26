from django.contrib import admin
from .models import MovimientoInventario


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = (
        "producto",
        "sucursal",
        "tipo_movimiento",
        "cantidad_delta",
        "responsable_nombre",
        "creado_en",
    )
    list_filter = ("tipo_movimiento", "sucursal")
    search_fields = ("producto__nombre", "producto__sku", "responsable_nombre", "motivo")