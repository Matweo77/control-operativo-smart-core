import uuid
from django.db import models
from organizacion.models import Sucursal, PerfilUsuario
from catalogo.models import Producto


class MovimientoInventario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column="sucursal_id", related_name="movimientos"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column="producto_id", related_name="movimientos"
    )
    usuario = models.ForeignKey(
        PerfilUsuario,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="usuario_id",
        related_name="movimientos",
    )
    responsable_nombre = models.TextField()
    tipo_movimiento = models.TextField()
    cantidad_delta = models.IntegerField()
    motivo = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "movimientos_inventario"
        managed = False