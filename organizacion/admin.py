from django.contrib import admin
from .models import Empresa, PerfilUsuario, Sucursal


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre_negocio", "nit_fiscal", "telefono", "id", "actualizado_en")
    search_fields = ("nombre_negocio", "nit_fiscal")


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "activa", "id", "creado_en")
    list_filter = ("activa", "empresa")
    search_fields = ("nombre",)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "email", "rol", "empresa", "sucursal", "activo")
    list_filter = ("rol", "activo", "empresa")
    search_fields = ("nombre_completo", "email")