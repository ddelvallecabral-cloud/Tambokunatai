"""Reglas del inventario de insumos. Todo cambio de stock pasa por acá y queda auditado."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.core import auditoria
from apps.core.mixins import ReglaNegocio

from .models import CERO, Insumo, Item, Motivo, MovimientoInventario, TipoMovimiento

_DEC = DecimalField(max_digits=14, decimal_places=3)


def _suma(tipo):
    return Coalesce(Sum("movimientos__cantidad", filter=Q(movimientos__tipo=tipo)), Value(CERO), output_field=_DEC)


def con_stock(qs=None):
    """Agrega stock, reservado y disponible a cada insumo en una sola consulta."""
    qs = Insumo.objects.all() if qs is None else qs
    return qs.annotate(
        _entradas=_suma(TipoMovimiento.ENTRADA), _salidas=_suma(TipoMovimiento.SALIDA),
        _reservas=_suma(TipoMovimiento.RESERVA), _liberaciones=_suma(TipoMovimiento.LIBERACION),
    ).annotate(
        stock=F("_entradas") - F("_salidas"),
        reservado=F("_reservas") - F("_liberaciones"),
    ).annotate(
        disponible=F("stock") - F("reservado"),
        bajo_minimo=Case(When(stock__lt=F("stock_minimo"), then=Value(True)), default=Value(False)),
    )


def stock_de(insumo: Insumo) -> dict:
    fila = con_stock(Insumo.objects.filter(pk=insumo.pk)).values("stock", "reservado", "disponible").get()
    return fila


def reservado_por_lote(insumo: Insumo, lote_queso) -> Decimal:
    movs = MovimientoInventario.objects.filter(insumo=insumo, lote_queso=lote_queso)
    r = movs.filter(tipo=TipoMovimiento.RESERVA).aggregate(t=Sum("cantidad"))["t"] or CERO
    l_ = movs.filter(tipo=TipoMovimiento.LIBERACION).aggregate(t=Sum("cantidad"))["t"] or CERO
    return r - l_


def consumido_por_lote(insumo: Insumo, lote_queso) -> Decimal:
    """Consumo neto de un insumo en un lote de queso (salidas menos devoluciones por corrección)."""
    movs = MovimientoInventario.objects.filter(insumo=insumo, lote_queso=lote_queso)
    s = movs.filter(tipo=TipoMovimiento.SALIDA).aggregate(t=Sum("cantidad"))["t"] or CERO
    e = movs.filter(tipo=TipoMovimiento.ENTRADA).aggregate(t=Sum("cantidad"))["t"] or CERO
    return s - e


def registrar(usuario, *, item, tipo, motivo, cantidad, unidad, **refs) -> MovimientoInventario:
    cantidad = Decimal(cantidad)
    if cantidad <= 0:
        raise ReglaNegocio("La cantidad tiene que ser mayor a cero.")
    mov = MovimientoInventario.objects.create(
        item=item, tipo=tipo, motivo=motivo, cantidad=cantidad, unidad=unidad, usuario=usuario, **refs
    )
    auditoria.registrar(
        "movimiento_inventario", "movimientos_inventario", mov.pk,
        cambios={
            "item": item, "tipo": tipo, "motivo": motivo, "cantidad": cantidad, "unidad": unidad,
            **{k: (getattr(v, "pk", v)) for k, v in refs.items() if v not in (None, "")},
        },
    )
    return mov


def _bloquear(insumo: Insumo) -> Insumo:
    """Serializa los movimientos de un mismo insumo para que dos lotes no reserven el mismo stock."""
    return Insumo.objects.select_for_update().get(pk=insumo.pk)


@transaction.atomic
def entrada(usuario, insumo: Insumo, cantidad, *, motivo=Motivo.COMPRA, lote_proveedor="", nota=""):
    insumo = _bloquear(insumo)
    if motivo not in (Motivo.COMPRA, Motivo.AJUSTE):
        raise ReglaNegocio("Una entrada manual es por compra o por ajuste.")
    if motivo == Motivo.AJUSTE and not nota.strip():
        raise ReglaNegocio("Para un ajuste hace falta explicar el motivo.")
    return registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.ENTRADA, motivo=motivo, cantidad=cantidad,
                     unidad=insumo.unidad, insumo=insumo, lote_proveedor=lote_proveedor, nota=nota)


@transaction.atomic
def salida_por_ajuste(usuario, insumo: Insumo, cantidad, *, nota: str):
    insumo = _bloquear(insumo)
    if not nota.strip():
        raise ReglaNegocio("Para un ajuste hace falta explicar el motivo.")
    disponible = stock_de(insumo)["disponible"]
    if Decimal(cantidad) > disponible:
        raise ReglaNegocio(f"Solo hay {disponible} {insumo.unidad} disponibles de {insumo.nombre}.")
    return registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.SALIDA, motivo=Motivo.AJUSTE,
                     cantidad=cantidad, unidad=insumo.unidad, insumo=insumo, nota=nota)


def reservar(usuario, insumo: Insumo, cantidad, lote_queso):
    insumo = _bloquear(insumo)
    if not insumo.activo:
        raise ReglaNegocio(f"{insumo.nombre} está dado de baja.")
    disponible = stock_de(insumo)["disponible"]
    if Decimal(cantidad) > disponible:
        raise ReglaNegocio(
            f"No alcanza {insumo.nombre}: hay {disponible.normalize():f} {insumo.unidad} disponibles "
            f"y se pidieron {Decimal(cantidad).normalize():f}."
        )
    return registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.RESERVA, motivo=Motivo.ELABORACION,
                     cantidad=cantidad, unidad=insumo.unidad, insumo=insumo, lote_queso=lote_queso)


def liberar_reservas(usuario, lote_queso, motivo=Motivo.ELABORACION) -> None:
    """Devuelve al stock disponible todo lo que el lote tenía reservado."""
    ids = (MovimientoInventario.objects.filter(lote_queso=lote_queso, item=Item.INSUMO)
           .values_list("insumo", flat=True).distinct())
    for insumo in Insumo.objects.filter(pk__in=list(ids)).order_by("pk"):
        insumo = _bloquear(insumo)
        pendiente = reservado_por_lote(insumo, lote_queso)
        if pendiente > 0:
            registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.LIBERACION, motivo=motivo,
                      cantidad=pendiente, unidad=insumo.unidad, insumo=insumo, lote_queso=lote_queso)


def fijar_consumo(usuario, insumo: Insumo, cantidad, lote_queso, motivo=Motivo.ELABORACION) -> Decimal:
    """Deja el consumo del insumo en el lote igual a `cantidad`, moviendo solo la diferencia.
    Se llama después de liberar las reservas del lote. Devuelve la diferencia aplicada."""
    insumo = _bloquear(insumo)
    actual = consumido_por_lote(insumo, lote_queso)
    diferencia = Decimal(cantidad) - actual
    if diferencia > 0:
        disponible = stock_de(insumo)["disponible"]
        if diferencia > disponible:
            raise ReglaNegocio(
                f"No alcanza {insumo.nombre}: hay {disponible.normalize():f} {insumo.unidad} disponibles "
                f"y el lote necesita {diferencia.normalize():f} más."
            )
        registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.SALIDA, motivo=motivo,
                  cantidad=diferencia, unidad=insumo.unidad, insumo=insumo, lote_queso=lote_queso)
    elif diferencia < 0:
        registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.CORRECCION,
                  cantidad=-diferencia, unidad=insumo.unidad, insumo=insumo, lote_queso=lote_queso,
                  nota="Devolución por corrección del consumo")
    return diferencia
