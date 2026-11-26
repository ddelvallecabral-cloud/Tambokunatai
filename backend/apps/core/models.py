import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Establecimiento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=120)
    ruc = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "establecimientos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Configuracion(models.Model):
    """Parámetros de negocio editables por el Administrador (umbrales, presupuestos, días de crédito)."""

    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, related_name="configuraciones")
    clave = models.CharField(max_length=80)
    valor = models.JSONField()
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "configuracion"
        constraints = [models.UniqueConstraint(fields=["establecimiento", "clave"], name="configuracion_clave_unica")]

    def __str__(self):
        return f"{self.clave}={self.valor}"


class Auditoria(models.Model):
    """Registro inmutable de cada acción. Ver apps.core.auditoria para cómo se escribe.

    La base de datos rechaza UPDATE, DELETE y TRUNCATE sobre esta tabla (trigger en la migración 0002).
    """

    id = models.BigAutoField(primary_key=True)
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    rol_activo = models.CharField(max_length=40, blank=True)
    accion = models.CharField(max_length=40, db_index=True)
    entidad = models.CharField(max_length=60, db_index=True)
    entidad_id = models.CharField(max_length=64, blank=True, db_index=True)
    cambios = models.JSONField(default=dict, blank=True)
    snapshot = models.JSONField(null=True, blank=True)
    motivo = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    dispositivo = models.CharField(max_length=255, blank=True)
    request_id = models.UUIDField(null=True, blank=True, db_index=True)
    registrado_offline_en = models.DateTimeField(null=True, blank=True)
    hash_anterior = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64)

    class Meta:
        db_table = "auditoria"
        ordering = ["-id"]
        verbose_name_plural = "auditoría"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("La auditoría es de solo inserción: no se puede modificar un registro existente.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("La auditoría es de solo inserción: no se puede borrar.")

    def __str__(self):
        return f"#{self.id} {self.accion} {self.entidad}:{self.entidad_id}"
