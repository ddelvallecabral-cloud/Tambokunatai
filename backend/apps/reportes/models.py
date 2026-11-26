from django.conf import settings
from django.db import models
from django.utils import timezone


class RevisionRegistro(models.Model):
    """Marca que el Administrador ya miró un cambio hecho sobre un registro cerrado.
    La auditoría es inmutable, por eso la marca va en esta tabla aparte."""

    auditoria = models.OneToOneField("core.Auditoria", on_delete=models.PROTECT, related_name="revision")
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    fecha = models.DateTimeField(default=timezone.now)
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "revisiones_registro"
