import uuid
from django.db import models
from organizacion.models import Empresa


class Cliente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, db_column="empresa_id", related_name="clientes"
    )
    codigo_cliente = models.TextField(blank=True, null=True)
    nombre_completo = models.TextField()
    documento = models.TextField(blank=True, null=True)
    telefono = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    total_compras = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    saldo_pendiente = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado = models.TextField(default="activo")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clientes"
        managed = False