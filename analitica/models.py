import uuid
from django.db import models
from organizacion.models import Sucursal
from catalogo.models import Producto


class PrediccionAgotamiento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column="sucursal_id", related_name="predicciones"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column="producto_id", related_name="predicciones"
    )
    unidades_restantes = models.IntegerField()
    velocidad_rotacion = models.TextField()
    dias_estimados = models.IntegerField()
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "predicciones_agotamiento"
        managed = False