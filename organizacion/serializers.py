from rest_framework import serializers
from .models import Empresa, PerfilUsuario, Sucursal


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = [
            "id",
            "nombre_negocio",
            "nit_fiscal",
            "direccion",
            "telefono",
            "logo_url",
            "actualizado_en",
        ]
        read_only_fields = ["id", "actualizado_en"]


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = [
            "id",
            "empresa",
            "nombre",
            "activa",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(
        source="sucursal.nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = PerfilUsuario
        fields = [
            "id",
            "empresa",
            "sucursal",
            "sucursal_nombre",
            "nombre_completo",
            "email",
            "rol",
            "activo",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]
        extra_kwargs = {
            "empresa": {"required": False, "allow_null": True},
        }

    def validate_rol(self, value):
        if not value:
            return "vendedor"
        return str(value).strip().lower()