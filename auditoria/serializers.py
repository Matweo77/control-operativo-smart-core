from rest_framework import serializers
from .models import MovimientoInventario


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    producto_sku = serializers.CharField(source="producto.sku", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    stock_antes = serializers.SerializerMethodField()
    stock_despues = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoInventario
        fields = [
            "id",
            "sucursal",
            "sucursal_nombre",
            "producto",
            "producto_sku",
            "producto_nombre",
            "usuario",
            "responsable_nombre",
            "cliente_nombre",
            "tipo_movimiento",
            "cantidad_delta",
            "stock_antes",
            "stock_despues",
            "motivo",
            "creado_en",
        ]
        read_only_fields = fields

    def get_cliente_nombre(self, obj):
        return getattr(obj, "_cliente_nombre_resuelto", None)

    def get_stock_antes(self, obj):
        return getattr(obj, "_stock_antes_resuelto", None)

    def get_stock_despues(self, obj):
        return getattr(obj, "_stock_despues_resuelto", None)