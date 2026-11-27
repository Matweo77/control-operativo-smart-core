from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_cliente",
        "nombre_completo",
        "documento",
        "telefono",
        "total_compras",
        "saldo_pendiente",
        "estado",
    )
    search_fields = ("nombre_completo", "documento", "telefono", "email", "codigo_cliente")
    list_filter = ("estado",)