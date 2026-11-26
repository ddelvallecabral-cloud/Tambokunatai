import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.mixins import AuditableModel, EstadoRegistro


class Ordene(models.TextChoices):
    MANANA = "manana", "Mañana"
    TARDE = "tarde", "Tarde"


class TipoDestino(models.TextChoices):
    VENTA = "venta", "Venta"
    ELABORACION_QUESO = "elaboracion_queso", "Elaboración de queso"
    DESCARTE = "descarte", "Descarte"


# Destino "resumido" de un lote, calculado a partir de sus asignaciones.
DESTINO_PENDIENTE = "pendiente"
DESTINO_MIXTO = "mixto"

CERO = Decimal("0")


class LoteLeche(AuditableModel):
    """Leche de una sesión de ordeñe. Un lote por fecha y ordeñe.

    Estados (heredados de AuditableModel):
      borrador  = abierto, se puede cargar y asignar destinos
      pendiente = tiene una corrección esperando aprobación del Administrador
      aprobado  = se aprobó una corrección; solo el Administrador lo edita
      rechazado = se rechazó una corrección; se puede volver a corregir
      cerrado   = todos los litros tienen destino; solo el Administrador lo edita
      anulado   = cargado por error
    """

    # El id lo puede generar el celular: así un reintento sin señal no duplica el lote.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    establecimiento = models.ForeignKey(
        "core.Establecimiento", null=True, blank=True, on_delete=models.PROTECT, related_name="lotes_leche"
    )
    fecha = models.DateField(db_index=True)
    ordene = models.CharField("ordeñe", max_length=10, choices=Ordene.choices)
    litros = models.DecimalField(max_digits=9, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))])
    grasa_pct = models.DecimalField(
        "grasa (%)", max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(15)],
    )
    proteina_pct = models.DecimalField(
        "proteína (%)", max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    temperatura_c = models.DecimalField(
        "temperatura (°C)", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(-5), MaxValueValidator(45)],
    )
    observaciones = models.TextField(blank=True)
    # Corrección que un Operador propuso sobre un lote de un día anterior; se aplica solo si el
    # Administrador la aprueba. Formato: {"campo": nuevo_valor, ..., "_motivo": "..."}
    cambios_propuestos = models.JSONField(null=True, blank=True, editable=False)
    propuesto_por = models.ForeignKey(
        "cuentas.Usuario", null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )

    CAMPOS_EDITABLES = ("fecha", "ordene", "litros", "grasa_pct", "proteina_pct", "temperatura_c", "observaciones")

    class Meta:
        db_table = "lotes_leche"
        ordering = ["-fecha", "-ordene"]
        constraints = [
            models.CheckConstraint(condition=Q(litros__gt=0), name="lote_leche_litros_positivos"),
            models.UniqueConstraint(
                fields=["fecha", "ordene"], condition=~Q(estado=EstadoRegistro.ANULADO),
                name="lote_leche_unico_por_ordene",
            ),
        ]

    def __str__(self):
        return self.codigo

    @property
    def codigo(self) -> str:
        return f"LL-{self.fecha:%Y%m%d}-{'M' if self.ordene == Ordene.MANANA else 'T'}"

    @property
    def litros_asignados(self) -> Decimal:
        if hasattr(self, "_asignados"):
            return self._asignados
        return self.destinos.aggregate(t=models.Sum("litros"))["t"] or CERO

    @property
    def saldo_disponible(self) -> Decimal:
        return self.litros - self.litros_asignados

    @property
    def destino(self) -> str:
        """pendiente, un tipo de destino, o mixto si los litros se repartieron entre varios."""
        tipos = {d.tipo for d in self.destinos.all()}
        if not tipos:
            return DESTINO_PENDIENTE
        return tipos.pop() if len(tipos) == 1 else DESTINO_MIXTO


class DestinoLeche(models.Model):
    """Cuántos litros de un lote se asignaron a cada destino. La suma nunca supera los litros del lote."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    lote = models.ForeignKey(LoteLeche, on_delete=models.CASCADE, related_name="destinos")
    tipo = models.CharField(max_length=20, choices=TipoDestino.choices)
    litros = models.DecimalField(max_digits=9, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))])
    nota = models.CharField(max_length=255, blank=True)
    creado_por = models.ForeignKey(
        "cuentas.Usuario", null=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "destinos_leche"
        ordering = ["fecha_creacion"]
        constraints = [models.CheckConstraint(condition=Q(litros__gt=0), name="destino_leche_litros_positivos")]

    def __str__(self):
        return f"{self.lote.codigo} → {self.tipo} {self.litros} L"
