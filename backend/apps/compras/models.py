"""Proveedores, compras de insumos y cuentas por pagar. Montos en guaraníes, sin decimales."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.archivos import ruta_comprobante_compra
from apps.core.mixins import AuditableModel


class TipoProveedor(models.TextChoices):
    INSUMOS = "insumos", "Insumos"
    SANIDAD = "sanidad", "Sanidad"
    SERVICIOS = "servicios", "Servicios"
    COMBUSTIBLE = "combustible", "Combustible"
    OTROS = "otros", "Otros"


class CondicionCompra(models.TextChoices):
    CONTADO = "contado", "Contado"
    CREDITO_15 = "credito_15", "Crédito 15 días"
    CREDITO_30 = "credito_30", "Crédito 30 días"
    CREDITO_60 = "credito_60", "Crédito 60 días"


DIAS_CONDICION = {"contado": 0, "credito_15": 15, "credito_30": 30, "credito_60": 60}


class Proveedor(AuditableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=TipoProveedor.choices, default=TipoProveedor.INSUMOS)
    ruc = models.CharField("RUC", max_length=30, blank=True)
    contacto = models.CharField("persona de contacto", max_length=120, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "proveedores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoCompra(models.TextChoices):
    CONFIRMADA = "confirmada", "Confirmada"
    ANULADA = "anulada", "Anulada"


class Compra(AuditableModel):
    """Una compra confirmada: sus insumos ya entraron al inventario y tiene su cuenta por pagar."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    numero = models.PositiveIntegerField(unique=True)
    fecha = models.DateField(db_index=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="compras")
    factura = models.CharField("n.º de factura", max_length=40, blank=True)
    condicion = models.CharField(max_length=12, choices=CondicionCompra.choices, default=CondicionCompra.CONTADO)
    total = models.PositiveBigIntegerField()
    observaciones = models.TextField(blank=True)
    comprobante = models.FileField(upload_to=ruta_comprobante_compra, blank=True)
    estado_compra = models.CharField(max_length=10, choices=EstadoCompra.choices, default=EstadoCompra.CONFIRMADA,
                                     db_index=True)

    class Meta:
        db_table = "compras"
        ordering = ["-fecha", "-numero"]

    def _valores(self) -> dict:
        valores = super()._valores()
        valores["comprobante"] = self.comprobante.name or ""
        return valores

    @property
    def codigo(self) -> str:
        return f"C-{self.numero:05d}"


class CompraItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    compra = models.ForeignKey(Compra, on_delete=models.PROTECT, related_name="items")
    insumo = models.ForeignKey("inventario.Insumo", on_delete=models.PROTECT, related_name="compras")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    precio_unitario = models.PositiveBigIntegerField()
    subtotal = models.PositiveBigIntegerField()
    lote_proveedor = models.CharField(max_length=60, blank=True)

    class Meta:
        db_table = "compra_items"
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="compra_item_cantidad_positiva")]


class EstadoCuentaPagar(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    PARCIAL = "parcial", "Pagada en parte"
    PAGADA = "pagada", "Pagada"
    ANULADA = "anulada", "Anulada"


class CuentaPorPagar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    compra = models.OneToOneField(Compra, on_delete=models.PROTECT, related_name="cuenta")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="cuentas")
    monto = models.PositiveBigIntegerField()
    pagado = models.PositiveBigIntegerField(default=0)
    fecha_emision = models.DateField()
    vencimiento = models.DateField(db_index=True)
    estado = models.CharField(max_length=10, choices=EstadoCuentaPagar.choices, default=EstadoCuentaPagar.PENDIENTE,
                              db_index=True)

    class Meta:
        db_table = "cuentas_por_pagar"
        ordering = ["vencimiento"]
        constraints = [models.CheckConstraint(condition=Q(pagado__lte=models.F("monto")), name="cuenta_pagado_no_supera_monto")]

    @property
    def saldo(self) -> int:
        return 0 if self.estado == EstadoCuentaPagar.ANULADA else self.monto - self.pagado


class Pago(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cuenta = models.ForeignKey(CuentaPorPagar, on_delete=models.PROTECT, related_name="pagos")
    fecha = models.DateField()
    monto = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    medio = models.CharField(max_length=15, choices=[("efectivo", "Efectivo"), ("transferencia", "Transferencia"),
                                                     ("cheque", "Cheque"), ("otro", "Otro")], default="efectivo")
    referencia = models.CharField(max_length=80, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    anulado = models.BooleanField(default=False)
    motivo_anulacion = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pagos"
        indexes = [models.Index(fields=["fecha"], name="pago_fecha_idx")]
        ordering = ["fecha", "fecha_creacion"]
