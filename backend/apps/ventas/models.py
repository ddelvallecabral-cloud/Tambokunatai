"""Clientes, precios, ventas, cuentas por cobrar y cobros. Montos en guaraníes, sin decimales."""
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.mixins import AuditableModel


class TipoCliente(models.TextChoices):
    MINORISTA = "minorista", "Minorista"
    MAYORISTA = "mayorista", "Mayorista"
    DISTRIBUIDOR = "distribuidor", "Distribuidor"
    TIENDA_PROPIA = "tienda_propia", "Tienda propia"


class CondicionPago(models.TextChoices):
    CONTADO = "contado", "Contado"
    CREDITO_7 = "credito_7", "Crédito 7 días"
    CREDITO_15 = "credito_15", "Crédito 15 días"
    CREDITO_30 = "credito_30", "Crédito 30 días"


DIAS_CREDITO = {"contado": 0, "credito_7": 7, "credito_15": 15, "credito_30": 30}


class Producto(models.TextChoices):
    LECHE = "leche", "Leche cruda"
    QUESO = "queso", "Queso Paraguay"


UNIDAD_PRODUCTO = {"leche": "l", "queso": "kg"}


class Cliente(AuditableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    nombre = models.CharField(max_length=120, db_index=True)
    tipo = models.CharField(max_length=15, choices=TipoCliente.choices, default=TipoCliente.MINORISTA)
    documento = models.CharField("RUC o CI", max_length=20, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    condicion_pago = models.CharField(max_length=12, choices=CondicionPago.choices, default=CondicionPago.CONTADO)
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True)

    class Meta:
        db_table = "clientes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Precio(AuditableModel):
    """Tabla de precios. Sin tipo de cliente = precio base. `cantidad_minima` > 0 = precio por volumen.
    Para una venta se toma la fila más específica que aplique (ver servicios.precio_para)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    producto = models.CharField(max_length=10, choices=Producto.choices)
    tipo_cliente = models.CharField(max_length=15, choices=TipoCliente.choices, blank=True, default="")
    cantidad_minima = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"),
                                          validators=[MinValueValidator(Decimal("0"))])
    precio_unitario = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "precios"
        ordering = ["producto", "tipo_cliente", "cantidad_minima"]
        constraints = [
            models.UniqueConstraint(fields=["producto", "tipo_cliente", "cantidad_minima"],
                                    condition=Q(activo=True), name="precio_unico_activo"),
        ]


class EstadoVenta(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente de entrega"
    ENTREGADA = "entregada", "Entregada"
    COBRADA = "cobrada", "Cobrada"
    ANULADA = "anulada", "Anulada"


class Venta(AuditableModel):
    """Una venta confirmada. Al registrarla se descuenta el inventario y nace su cuenta por cobrar."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    numero = models.PositiveIntegerField(unique=True)
    fecha = models.DateField(db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ventas")
    producto = models.CharField(max_length=10, choices=Producto.choices)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    precio_unitario = models.PositiveIntegerField()
    precio_de_lista = models.PositiveIntegerField(help_text="Precio que daba la tabla al momento de vender")
    total = models.PositiveBigIntegerField()
    estado_venta = models.CharField(max_length=10, choices=EstadoVenta.choices, default=EstadoVenta.PENDIENTE,
                                    db_index=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "ventas"
        ordering = ["-fecha", "-numero"]
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="venta_cantidad_positiva")]

    def __str__(self):
        return self.codigo

    @property
    def codigo(self) -> str:
        return f"V-{self.numero:05d}"

    @property
    def unidad(self) -> str:
        return UNIDAD_PRODUCTO[self.producto]


class VentaLote(models.Model):
    """De qué lote salió cada parte de una venta (trazabilidad venta → lote)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="lotes")
    lote_queso = models.ForeignKey("queso.LoteQueso", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="ventas")
    lote_leche = models.ForeignKey("leche.LoteLeche", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="ventas")
    # Para leche: el destino "venta" del lote de leche que se usó.
    destino = models.OneToOneField("leche.DestinoLeche", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="uso_venta")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        db_table = "venta_lotes"
        constraints = [
            models.CheckConstraint(
                condition=(Q(lote_queso__isnull=False) & Q(lote_leche__isnull=True))
                | (Q(lote_queso__isnull=True) & Q(lote_leche__isnull=False)),
                name="venta_lote_un_solo_origen"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="venta_lote_cantidad_positiva"),
        ]


class EstadoCuenta(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    PARCIAL = "parcial", "Cobrada en parte"
    COBRADA = "cobrada", "Cobrada"
    ANULADA = "anulada", "Anulada"


class CuentaPorCobrar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    venta = models.OneToOneField(Venta, on_delete=models.PROTECT, related_name="cuenta")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="cuentas")
    monto = models.PositiveBigIntegerField()
    cobrado = models.PositiveBigIntegerField(default=0)
    fecha_emision = models.DateField()
    vencimiento = models.DateField(db_index=True)
    estado = models.CharField(max_length=10, choices=EstadoCuenta.choices, default=EstadoCuenta.PENDIENTE,
                              db_index=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "cuentas_por_cobrar"
        ordering = ["vencimiento"]
        constraints = [models.CheckConstraint(condition=Q(cobrado__lte=models.F("monto")),
                                              name="cuenta_cobrado_no_supera_monto")]

    @property
    def saldo(self) -> int:
        return self.monto - self.cobrado


class MedioPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TRANSFERENCIA = "transferencia", "Transferencia"
    OTRO = "otro", "Otro"


class Cobro(models.Model):
    """Un pago recibido. No se edita ni se borra: un error se anula con motivo (Administrador)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cuenta = models.ForeignKey(CuentaPorCobrar, on_delete=models.PROTECT, related_name="cobros")
    fecha = models.DateField()
    monto = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    medio = models.CharField(max_length=15, choices=MedioPago.choices, default=MedioPago.EFECTIVO)
    referencia = models.CharField(max_length=60, blank=True)
    usuario = models.ForeignKey("cuentas.Usuario", null=True, on_delete=models.PROTECT, related_name="+")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    anulado = models.BooleanField(default=False)
    motivo_anulacion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "cobros"
        ordering = ["-fecha", "-fecha_creacion"]
        constraints = [models.CheckConstraint(condition=Q(monto__gt=0), name="cobro_monto_positivo")]
