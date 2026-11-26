import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.mixins import AuditableModel

CERO = Decimal("0")


class LoteQueso(AuditableModel):
    """Una tanda de elaboración de queso.

    Estados (heredados de AuditableModel):
      borrador  = en elaboración: la leche ya se descontó y los insumos están reservados
      pendiente = cerrado con kg obtenidos, esperando aprobación del Administrador
      aprobado  = aprobado: el queso queda disponible para vender
      rechazado = el Administrador lo devolvió con un comentario; se corrige y se vuelve a enviar
      anulado   = elaboración cancelada antes de cerrar
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    numero = models.PositiveSmallIntegerField(default=1, help_text="Número de lote del día")
    fecha = models.DateField(db_index=True)
    litros_leche = models.DecimalField(max_digits=9, decimal_places=1, default=CERO)
    kg_obtenidos = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(Decimal("0.01"))])
    merma_kg = models.DecimalField(max_digits=8, decimal_places=2, default=CERO,
                                   validators=[MinValueValidator(CERO)])
    rendimiento_l_kg = models.DecimalField("rendimiento (L/kg)", max_digits=6, decimal_places=2,
                                           null=True, blank=True)
    rendimiento_fuera_de_rango = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    cerrado_por = models.ForeignKey("cuentas.Usuario", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+", editable=False)
    fecha_cierre = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        db_table = "lotes_queso"
        ordering = ["-fecha", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["fecha", "numero"], name="lote_queso_numero_unico_por_dia"),
            models.CheckConstraint(condition=Q(merma_kg__gte=0), name="lote_queso_merma_no_negativa"),
            models.CheckConstraint(
                condition=Q(kg_obtenidos__isnull=True) | Q(kg_obtenidos__gt=0), name="lote_queso_kg_positivos"),
        ]

    def __str__(self):
        return self.codigo

    @property
    def codigo(self) -> str:
        return f"LQ-{self.fecha:%Y%m%d}-{self.numero}"

    @property
    def kg_netos(self):
        if self.kg_obtenidos is None:
            return None
        return self.kg_obtenidos - self.merma_kg


class LoteQuesoLeche(models.Model):
    """De qué lote de leche salió cada litro de un lote de queso (trazabilidad).
    Cada fila usa un destino "elaboración de queso" del lote de leche."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    lote_queso = models.ForeignKey(LoteQueso, on_delete=models.PROTECT, related_name="origenes")
    lote_leche = models.ForeignKey("leche.LoteLeche", on_delete=models.PROTECT, related_name="usos_queso")
    destino = models.OneToOneField("leche.DestinoLeche", null=True, on_delete=models.SET_NULL, related_name="uso_queso")
    litros = models.DecimalField(max_digits=9, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))])
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lote_queso_leche"
        ordering = ["lote_leche__fecha", "lote_leche__ordene"]
        constraints = [models.CheckConstraint(condition=Q(litros__gt=0), name="lote_queso_leche_litros_positivos")]


class LoteQuesoInsumo(models.Model):
    """Insumos de un lote: lo declarado al iniciar (se reserva) y lo consumido al cerrar."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    lote_queso = models.ForeignKey(LoteQueso, on_delete=models.CASCADE, related_name="insumos")
    insumo = models.ForeignKey("inventario.Insumo", on_delete=models.PROTECT, related_name="usos_queso")
    cantidad_declarada = models.DecimalField(max_digits=12, decimal_places=3, default=CERO)
    cantidad_consumida = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        db_table = "lote_queso_insumos"
        ordering = ["insumo__nombre"]
        constraints = [models.UniqueConstraint(fields=["lote_queso", "insumo"], name="lote_queso_insumo_unico")]
