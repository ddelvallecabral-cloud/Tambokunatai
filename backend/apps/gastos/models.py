"""Gastos operativos. Montos en guaraníes, sin decimales.

Estados (heredados de AuditableModel):
  pendiente = supera el umbral (GASTO_MONTO_APROBACION) y espera al Administrador
  aprobado  = aprobado por el Administrador, o automáticamente si no supera el umbral
  rechazado = devuelto con comentario; quien lo cargó lo puede corregir y volver a enviar
  anulado   = anulado por el Administrador, con motivo
"""
import uuid

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.archivos import ruta_comprobante_gasto
from apps.core.mixins import AuditableModel


class Categoria(models.TextChoices):
    ALIMENTACION = "alimentacion", "Alimentación del ganado"
    SANIDAD = "sanidad", "Sanidad"
    SERVICIOS = "servicios", "Servicios"
    MANTENIMIENTO = "mantenimiento", "Mantenimiento"
    HONORARIOS = "honorarios", "Honorarios"
    COMBUSTIBLE = "combustible", "Combustible"
    OTROS = "otros", "Otros"


class CentroCosto(models.TextChoices):
    LECHE = "produccion_leche", "Producción de leche"
    QUESO = "elaboracion_queso", "Elaboración de queso"
    ADMINISTRACION = "administracion", "Administración"


class Gasto(AuditableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    fecha = models.DateField(db_index=True)
    categoria = models.CharField(max_length=15, choices=Categoria.choices, db_index=True)
    centro_costo = models.CharField(max_length=20, choices=CentroCosto.choices, db_index=True)
    monto = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    descripcion = models.CharField(max_length=255)
    proveedor = models.ForeignKey("compras.Proveedor", null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="gastos")
    comprobante_numero = models.CharField("n.º de comprobante", max_length=60, blank=True)
    comprobante = models.FileField(upload_to=ruta_comprobante_gasto, blank=True)
    aprobacion_automatica = models.BooleanField(default=False)

    class Meta:
        db_table = "gastos"
        ordering = ["-fecha", "-fecha_creacion"]

    def _valores(self) -> dict:
        valores = super()._valores()
        valores["comprobante"] = self.comprobante.name or ""
        return valores
