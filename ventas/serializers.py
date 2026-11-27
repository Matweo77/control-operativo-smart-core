from decimal import Decimal
from rest_framework import serializers
from catalogo.models import Producto
from clientes.models import Cliente
from organizacion.models import PerfilUsuario, Sucursal
from .models import DetalleVenta, Venta

METODOS_PAGO_PERMITIDOS = {
    "efectivo": "efectivo",
    "cash": "efectivo",
    "tarjeta": "tarjeta",
    "debito": "tarjeta",
    "débito": "tarjeta",
    "transferencia": "transferencia",
    "nequi": "transferencia",
    "nequi / transferencia": "transferencia",
}


class DetalleVentaInputSerializer(serializers.Serializer):
    producto_id = serializers.UUIDField()
    cantidad = serializers.IntegerField(min_value=1)


class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(
        source="producto.nombre", read_only=True
    )
    producto_sku = serializers.CharField(source="producto.sku", read_only=True)

    class Meta:
        model = DetalleVenta
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "producto_sku",
            "cantidad",
            "precio_unitario",
            "costo_unitario",
            "subtotal_linea",
        ]
        read_only_fields = fields


class VentaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(
        source="cliente.nombre_completo", read_only=True, allow_null=True
    )
    usuario_nombre = serializers.CharField(
        source="usuario.nombre_completo", read_only=True, allow_null=True
    )
    detalles = DetalleVentaSerializer(many=True, read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id",
            "sucursal",
            "cliente",
            "cliente_nombre",
            "usuario",
            "usuario_nombre",
            "numero_ticket",
            "subtotal",
            "impuesto_iva",
            "total",
            "metodo_pago",
            "creado_en",
            "detalles",
        ]
        read_only_fields = [
            "id",
            "numero_ticket",
            "subtotal",
            "impuesto_iva",
            "total",
            "creado_en",
            "detalles",
        ]


class CrearVentaSerializer(serializers.Serializer):
    sucursal = serializers.PrimaryKeyRelatedField(
        queryset=Sucursal.objects.all(), required=False, allow_null=True
    )
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )
    usuario = serializers.PrimaryKeyRelatedField(
        queryset=PerfilUsuario.objects.all(), required=False, allow_null=True
    )
    responsable_nombre = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    metodo_pago = serializers.CharField(max_length=50)
    tasa_iva = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        required=False,
        default=Decimal("0.16"),
        min_value=Decimal("0"),
        max_value=Decimal("1"),
    )
    items = DetalleVentaInputSerializer(many=True, allow_empty=False)

    def validate_metodo_pago(self, value):
        limpio = (value or "").strip().lower()
        if not limpio:
            raise serializers.ValidationError("El método de pago es obligatorio.")
        normalizado = METODOS_PAGO_PERMITIDOS.get(limpio)
        if not normalizado:
            raise serializers.ValidationError(
                "Método de pago no válido. Usa 'efectivo', 'tarjeta' o 'transferencia'."
            )
        return normalizado

    def validate_items(self, items):
        agrupados = {}
        for item in items:
            pid = item["producto_id"]
            cant = int(item["cantidad"])
            if cant <= 0:
                raise serializers.ValidationError(
                    "Cada producto debe tener cantidad mayor a 0."
                )
            agrupados[pid] = agrupados.get(pid, 0) + cant

        ids = list(agrupados.keys())
        productos_existentes = set(
            Producto.objects.filter(id__in=ids).values_list("id", flat=True)
        )
        faltantes = [str(pid) for pid in ids if pid not in productos_existentes]
        if faltantes:
            raise serializers.ValidationError(
                f"Productos no encontrados: {', '.join(faltantes)}."
            )

        return [
            {"producto_id": pid, "cantidad": cant}
            for pid, cant in agrupados.items()
        ]