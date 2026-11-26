import uuid
from django.db import models


class Empresa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre_negocio = models.TextField()
    nit_fiscal = models.TextField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.TextField(blank=True, null=True)
    logo_url = models.TextField(blank=True, null=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "empresas"
        managed = False


class Sucursal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, db_column="empresa_id", related_name="sucursales"
    )
    nombre = models.TextField()
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sucursales"
        managed = False


class PerfilUsuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, db_column="empresa_id", related_name="usuarios"
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="sucursal_id",
        related_name="usuarios",
    )
    nombre_completo = models.TextField()
    email = models.TextField(unique=True, blank=True, null=True)
    rol = models.TextField()
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "perfiles_usuario"
        managed = False