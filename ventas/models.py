import uuid
from django.db import models
from organizacion.models import Sucursal, PerfilUsuario
from clientes.models import Cliente
from catalogo.models import Producto


class Venta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column="sucursal_id", related_name="ventas"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="cliente_id",
        related_name="ventas",
    )
    usuario = models.ForeignKey(
        PerfilUsuario,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="usuario_id",
        related_name="ventas",
    )
    numero_ticket = models.TextField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    impuesto_iva = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    metodo_pago = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ventas"
        managed = False


class DetalleVenta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, db_column="venta_id", related_name="detalles"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.RESTRICT, db_column="producto_id", related_name="detalles_venta"
    )
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal_linea = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "detalle_ventas"
        managed = False