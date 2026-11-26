"""Inventario: insumos y movimientos.

El stock nunca se guarda como un número que se pisa: se calcula sumando movimientos.
Los movimientos son de solo inserción (la base rechaza UPDATE y DELETE). Un error se
corrige con un movimiento contrario, así siempre queda el rastro.

- Insumos (cuajo, sal, cultivos, envases): stock = entradas - salidas;
  reservado = reservas - liberaciones; disponible = stock - reservado.
- Leche: cada salida hacia un lote de queso queda registrada con su lote de leche de origen.
  El saldo de cada lote de leche sale de sus destinos (Fase 2).
- Queso: la entrada al cerrar un lote de queso; las salidas por venta llegan en la Fase 4.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.mixins import AuditableModel

CERO = Decimal("0")


class Unidad(models.TextChoices):
    KG = "kg", "kg"
    G = "g", "g"
    L = "l", "litros"
    ML = "ml", "ml"
    UNIDAD = "unidad", "unidades"


class Insumo(AuditableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    categoria = models.CharField(
        max_length=20,
        choices=[("cuajo", "Cuajo"), ("sal", "Sal"), ("cultivo", "Cultivo"), ("aditivo", "Aditivo"),
                 ("envase", "Envase"), ("limpieza", "Limpieza"), ("otro", "Otro")],
        default="otro",
    )
    unidad = models.CharField(max_length=10, choices=Unidad.choices)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=CERO,
                                       validators=[MinValueValidator(CERO)])
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "insumos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_unidad_display()})"


class Item(models.TextChoices):
    INSUMO = "insumo", "Insumo"
    LECHE = "leche", "Leche"
    QUESO = "queso", "Queso"


class TipoMovimiento(models.TextChoices):
    ENTRADA = "entrada", "Entrada"
    SALIDA = "salida", "Salida"
    RESERVA = "reserva", "Reserva"
    LIBERACION = "liberacion", "Liberación de reserva"


class Motivo(models.TextChoices):
    COMPRA = "compra", "Compra"
    AJUSTE = "ajuste", "Ajuste de inventario"
    ELABORACION = "elaboracion", "Elaboración de queso"
    PRODUCCION = "produccion", "Producción de queso"
    CORRECCION = "correccion", "Corrección de un lote"
    CANCELACION = "cancelacion", "Cancelación de un lote"
    VENTA = "venta", "Venta"
    DEVOLUCION = "devolucion", "Devolución por venta anulada"
    MERMA = "merma", "Merma"
    ANULACION_COMPRA = "anul_compra", "Anulación de una compra"


class MovimientoInventario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    item = models.CharField(max_length=10, choices=Item.choices)
    tipo = models.CharField(max_length=12, choices=TipoMovimiento.choices)
    motivo = models.CharField(max_length=12, choices=Motivo.choices)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unidad = models.CharField(max_length=10, choices=Unidad.choices)
    insumo = models.ForeignKey(Insumo, null=True, blank=True, on_delete=models.PROTECT, related_name="movimientos")
    lote_leche = models.ForeignKey("leche.LoteLeche", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="movimientos_inventario")
    lote_queso = models.ForeignKey("queso.LoteQueso", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="movimientos_inventario")
    venta = models.ForeignKey("ventas.Venta", null=True, blank=True, on_delete=models.PROTECT,
                              related_name="movimientos_inventario")
    compra = models.ForeignKey("compras.Compra", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="movimientos_inventario")
    lote_proveedor = models.CharField("lote del proveedor", max_length=60, blank=True)
    nota = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "movimientos_inventario"
        ordering = ["-fecha"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="movimiento_cantidad_positiva"),
            # Cada movimiento queda atado a lo que mueve y a su lote de origen cuando aplica.
            models.CheckConstraint(
                condition=~Q(item="insumo") | Q(insumo__isnull=False), name="movimiento_insumo_con_insumo"),
            models.CheckConstraint(
                condition=~Q(item="leche") | Q(lote_leche__isnull=False), name="movimiento_leche_con_lote"),
            models.CheckConstraint(
                condition=~Q(item="queso") | Q(lote_queso__isnull=False), name="movimiento_queso_con_lote"),
            # Reservar o consumir para elaborar siempre dice para qué lote de queso fue.
            models.CheckConstraint(
                condition=~Q(motivo__in=["elaboracion", "produccion", "cancelacion", "correccion"])
                | Q(lote_queso__isnull=False),
                name="movimiento_elaboracion_con_lote_queso"),
            models.CheckConstraint(
                condition=~Q(motivo__in=["venta", "devolucion"]) | Q(venta__isnull=False),
                name="movimiento_venta_con_venta"),
            models.CheckConstraint(
                condition=~Q(motivo="anul_compra") | Q(compra__isnull=False),
                name="movimiento_anulacion_con_compra"),
            models.CheckConstraint(
                condition=Q(item="insumo") | Q(tipo__in=["entrada", "salida"]),
                name="movimiento_reserva_solo_insumos"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Los movimientos de inventario no se modifican: registrá un movimiento contrario.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Los movimientos de inventario no se borran: registrá un movimiento contrario.")

    def __str__(self):
        return f"{self.tipo} {self.cantidad} {self.unidad} {self.item}"
