import re
from rest_framework import serializers
from organizacion.models import Empresa
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    empresa = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Cliente
        fields = [
            "id",
            "empresa",
            "codigo_cliente",
            "nombre_completo",
            "documento",
            "telefono",
            "email",
            "total_compras",
            "saldo_pendiente",
            "estado",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]

    def validate_estado(self, value):
        normalizado = (value or "activo").strip().lower()
        if normalizado not in ("activo", "inactivo"):
            raise serializers.ValidationError(
                "El estado debe ser 'activo' o 'inactivo'."
            )
        return normalizado

    def _generar_codigo_cliente(self, empresa):
        codigos = Cliente.objects.filter(empresa=empresa).values_list(
            "codigo_cliente", flat=True
        )
        max_num = 0
        for codigo in codigos:
            if not codigo:
                continue
            match = re.search(r"(\d+)$", codigo.strip())
            if match:
                max_num = max(max_num, int(match.group(1)))

        siguiente = max_num + 1
        while Cliente.objects.filter(
            empresa=empresa, codigo_cliente=f"Cliente #{siguiente:03d}"
        ).exists():
            siguiente += 1

        return f"Cliente #{siguiente:03d}"

    def create(self, validated_data):
        empresa = validated_data.get("empresa") or Empresa.objects.first()
        if not empresa:
            raise serializers.ValidationError(
                {"empresa": "No hay ninguna empresa registrada en el sistema."}
            )
        validated_data["empresa"] = empresa

        if not validated_data.get("codigo_cliente"):
            validated_data["codigo_cliente"] = self._generar_codigo_cliente(empresa)

        return super().create(validated_data)