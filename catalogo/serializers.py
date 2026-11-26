from django.db.models import Sum
from rest_framework import serializers
from .models import Categoria, InventarioSucursal, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "empresa", "nombre", "creado_en"]
        read_only_fields = ["id", "creado_en"]


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(
        source="categoria.nombre", read_only=True, default=None
    )
    margen_porcentaje = serializers.SerializerMethodField()
    stock_actual = serializers.SerializerMethodField()
    estado_stock = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "empresa",
            "categoria",
            "categoria_nombre",
            "sku",
            "codigo_barras",
            "nombre",
            "imagen_url",
            "precio_costo",
            "precio_venta",
            "margen_porcentaje",
            "stock_minimo",
            "stock_actual",
            "estado_stock",
            "activo",
            "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]

    def get_margen_porcentaje(self, obj):
        if obj.precio_venta and obj.precio_venta > 0:
            margen = ((obj.precio_venta - obj.precio_costo) / obj.precio_venta) * 100
            return round(float(margen), 1)
        return 0.0

    def _get_total_stock(self, obj):
        if hasattr(obj, "_stock_total_cache"):
            return obj._stock_total_cache

        inventarios = getattr(obj, "inventarios", None)
        if inventarios is not None:
            total = inventarios.aggregate(total=Sum("stock_actual"))["total"]
            if total is not None:
                obj._stock_total_cache = int(total)
                return obj._stock_total_cache

        obj._stock_total_cache = 0
        return 0

    def get_stock_actual(self, obj):
        return self._get_total_stock(obj)

    def get_estado_stock(self, obj):
        stock = self._get_total_stock(obj)
        minimo = obj.stock_minimo if obj.stock_minimo is not None else 5
        if stock <= 0:
            return "agotado"
        if stock <= minimo:
            return "bajo"
        return "normal"