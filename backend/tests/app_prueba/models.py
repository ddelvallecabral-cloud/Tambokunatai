"""Entidad de ejemplo usada solo en las pruebas del AuditableModel."""
from django.db import models

from apps.core.mixins import AuditableModel


class Documento(AuditableModel):
    titulo = models.CharField(max_length=80)
    monto = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "prueba_documento"
