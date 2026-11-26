import uuid
from django.db import models
from organizacion.models import Empresa, Sucursal


class Categoria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, db_column="empresa_id", related_name="categorias"
    )
    nombre = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categorias"
        managed = False


class Producto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, db_column="empresa_id", related_name="productos"
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="categoria_id",
        related_name="productos",
    )
    sku = models.TextField()
    codigo_barras = models.TextField(blank=True, null=True)
    nombre = models.TextField()
    imagen_url = models.TextField(blank=True, null=True)
    precio_costo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_minimo = models.IntegerField(default=5)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "productos"
        managed = False


class InventarioSucursal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column="sucursal_id", related_name="inventarios"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column="producto_id", related_name="inventarios"
    )
    stock_actual = models.IntegerField(default=0)
    estado_stock = models.TextField(default="normal")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventario_sucursal"
        managed = False