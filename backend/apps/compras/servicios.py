"""Compras de insumos: al registrarla queda confirmada, los insumos entran al inventario y nace la
cuenta por pagar, todo en la misma transacción."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection, transaction
from django.db.models import Max, Sum

from apps.core import auditoria
from apps.core.archivos import validar_comprobante
from apps.core.mixins import ReglaNegocio
from apps.inventario import servicios as inventario
from apps.inventario.models import Insumo, Item, Motivo, TipoMovimiento
from apps.leche import servicios as leche

from .models import (
    DIAS_CONDICION, Compra, CompraItem, CuentaPorPagar, EstadoCompra, EstadoCuentaPagar, Pago, Proveedor,
)

PERMISO_PAGOS = "compras.pago.registrar"
PERMISO_ANULAR = "compras.compra.aprobar"
_CANDADO_NUMERO = 7_340_051


def hoy():
    return leche.hoy()


def _siguiente_numero() -> int:
    with connection.cursor() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", [_CANDADO_NUMERO])
    return (Compra.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


def _subtotal(cantidad: Decimal, precio: int) -> int:
    return int((Decimal(cantidad) * precio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@transaction.atomic
def registrar_compra(usuario, *, proveedor, items: list[dict], fecha=None, factura: str = "",
                     condicion: str = "contado", pagada: bool = False, medio: str = "efectivo",
                     observaciones: str = "", comprobante=None, id=None) -> tuple[Compra, bool]:
    """items: [{"insumo": Insumo | id, "cantidad": Decimal, "precio_unitario": int, "lote_proveedor": str}]."""
    if id is not None and (existente := Compra.objects.filter(pk=id).first()):
        return existente, False
    proveedor = proveedor if isinstance(proveedor, Proveedor) else Proveedor.objects.filter(pk=proveedor).first()
    if proveedor is None or not proveedor.activo:
        raise ReglaNegocio("El proveedor no existe o está dado de baja.")
    fecha = fecha or hoy()
    if fecha > hoy():
        raise ReglaNegocio("No se puede registrar una compra con fecha futura.")
    if not items:
        raise ReglaNegocio("Cargá al menos un insumo.")
    ids = [str(getattr(i["insumo"], "pk", i["insumo"])) for i in items]
    if len(set(ids)) != len(ids):
        raise ReglaNegocio("Hay un insumo repetido en la compra.")
    insumos = {str(i.pk): i for i in Insumo.objects.filter(pk__in=ids)}
    filas = []
    for i, ident in zip(items, ids):
        insumo = insumos.get(ident)
        if insumo is None or not insumo.activo:
            raise ReglaNegocio("Uno de los insumos no existe o está dado de baja.")
        cantidad, precio = Decimal(i["cantidad"]), int(i["precio_unitario"])
        if cantidad <= 0:
            raise ReglaNegocio(f"La cantidad de {insumo.nombre} tiene que ser mayor a cero.")
        if precio <= 0:
            raise ReglaNegocio(f"El precio de {insumo.nombre} tiene que ser mayor a cero.")
        filas.append((insumo, cantidad, precio, (i.get("lote_proveedor") or "").strip()))
    tipo_comprobante = validar_comprobante(comprobante) if comprobante else ""

    total = sum(_subtotal(c, p) for _, c, p, _ in filas)
    compra = Compra(numero=_siguiente_numero(), fecha=fecha, proveedor=proveedor, factura=factura.strip(),
                    condicion=condicion, total=total, observaciones=observaciones)
    if id is not None:
        compra.id = id
    if comprobante:
        compra._tipo_comprobante = tipo_comprobante
        compra.comprobante = comprobante
    compra.save()

    for insumo, cantidad, precio, lote in filas:
        CompraItem.objects.create(compra=compra, insumo=insumo, cantidad=cantidad, precio_unitario=precio,
                                  subtotal=_subtotal(cantidad, precio), lote_proveedor=lote)
        Insumo.objects.select_for_update().get(pk=insumo.pk)
        inventario.registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.COMPRA,
                             cantidad=cantidad, unidad=insumo.unidad, insumo=insumo, compra=compra,
                             lote_proveedor=lote, nota=f"{compra.codigo} · {proveedor.nombre}")

    cuenta = CuentaPorPagar.objects.create(
        compra=compra, proveedor=proveedor, monto=total, fecha_emision=fecha,
        vencimiento=fecha + datetime.timedelta(days=DIAS_CONDICION[condicion]),
    )
    auditoria.registrar("registrar_compra", "compras", compra.pk, cambios={
        "proveedor": proveedor.nombre, "total": total, "vencimiento": cuenta.vencimiento,
        "items": {ins.codigo: [str(c), p] for ins, c, p, _ in filas},
    })
    if pagada:
        _pagar(usuario, cuenta, monto=total, fecha=fecha, medio=medio)
    return Compra.objects.get(pk=compra.pk), True


def _recalcular(cuenta: CuentaPorPagar) -> None:
    pagado = cuenta.pagos.filter(anulado=False).aggregate(t=Sum("monto"))["t"] or 0
    cuenta.pagado = pagado
    if cuenta.estado != EstadoCuentaPagar.ANULADA:
        cuenta.estado = (EstadoCuentaPagar.PAGADA if pagado >= cuenta.monto
                         else EstadoCuentaPagar.PARCIAL if pagado else EstadoCuentaPagar.PENDIENTE)
    cuenta.save(update_fields=["pagado", "estado"])


def _pagar(usuario, cuenta, *, monto, fecha=None, medio="efectivo", referencia="") -> Pago:
    cuenta = CuentaPorPagar.objects.select_for_update().get(pk=cuenta.pk)
    if cuenta.estado == EstadoCuentaPagar.ANULADA:
        raise ReglaNegocio("La cuenta está anulada.")
    monto = int(monto)
    if monto <= 0:
        raise ReglaNegocio("El monto tiene que ser mayor a cero.")
    if monto > cuenta.saldo:
        raise ReglaNegocio(f"El saldo es Gs. {cuenta.saldo:,}".replace(",", ".") + ": no se puede pagar más.")
    fecha = fecha or hoy()
    if fecha > hoy():
        raise ReglaNegocio("No se puede registrar un pago con fecha futura.")
    pago = Pago.objects.create(cuenta=cuenta, fecha=fecha, monto=monto, medio=medio, referencia=referencia, usuario=usuario)
    _recalcular(cuenta)
    auditoria.registrar("registrar_pago", "cuentas_por_pagar", cuenta.pk, cambios={
        "compra": cuenta.compra.codigo, "monto": monto, "medio": medio, "saldo": [cuenta.saldo + monto, cuenta.saldo]})
    return pago


@transaction.atomic
def registrar_pago(usuario, cuenta: CuentaPorPagar, **datos) -> Pago:
    if not usuario.tiene_permiso(PERMISO_PAGOS):
        raise ReglaNegocio("Solo el Administrador registra pagos a proveedores.")
    return _pagar(usuario, cuenta, **datos)


@transaction.atomic
def anular_pago(usuario, pago: Pago, motivo: str) -> Pago:
    if not usuario.tiene_permiso(PERMISO_PAGOS):
        raise ReglaNegocio("Solo el Administrador anula pagos.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para anular un pago hace falta el motivo.")
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    if pago.anulado:
        raise ReglaNegocio("El pago ya está anulado.")
    pago.anulado, pago.motivo_anulacion = True, motivo
    pago.save(update_fields=["anulado", "motivo_anulacion"])
    _recalcular(pago.cuenta)
    auditoria.registrar("anular_pago", "cuentas_por_pagar", pago.cuenta_id,
                        cambios={"pago": pago.pk, "monto": pago.monto}, motivo=motivo)
    return pago


@transaction.atomic
def anular_compra(usuario, compra: Compra, motivo: str) -> Compra:
    """Saca del inventario lo que entró con la compra y anula la cuenta. Antes hay que anular los pagos,
    y solo se puede si esos insumos todavía están disponibles (no se usaron)."""
    if not usuario.tiene_permiso(PERMISO_ANULAR):
        raise ReglaNegocio("Solo el Administrador anula compras.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para anular una compra hace falta el motivo.")
    compra = Compra.objects.select_for_update().get(pk=compra.pk)
    if compra.estado_compra == EstadoCompra.ANULADA:
        raise ReglaNegocio("La compra ya está anulada.")
    if compra.cuenta.pagos.filter(anulado=False).exists():
        raise ReglaNegocio("La compra tiene pagos registrados: anulalos primero.")
    for item in compra.items.select_related("insumo"):
        insumo = Insumo.objects.select_for_update().get(pk=item.insumo_id)
        disponible = inventario.stock_de(insumo)["disponible"]
        if item.cantidad > disponible:
            raise ReglaNegocio(
                f"De {insumo.nombre} quedan {disponible.normalize():f} {insumo.unidad} disponibles y la compra trajo "
                f"{item.cantidad.normalize():f}: ya se usó una parte. Corregí el stock con un ajuste en vez de anular.")
        inventario.registrar(usuario, item=Item.INSUMO, tipo=TipoMovimiento.SALIDA, motivo=Motivo.ANULACION_COMPRA,
                             cantidad=item.cantidad, unidad=insumo.unidad, insumo=insumo, compra=compra,
                             nota=f"Anulación {compra.codigo}")
    cuenta = compra.cuenta
    cuenta.estado = EstadoCuentaPagar.ANULADA
    cuenta.save(update_fields=["estado"])
    compra.estado_compra = EstadoCompra.ANULADA
    compra.save()
    compra.anular(motivo)
    return compra


def resumen_cuentas(fecha=None) -> dict:
    fecha = fecha or hoy()
    abiertas = CuentaPorPagar.objects.filter(
        estado__in=[EstadoCuentaPagar.PENDIENTE, EstadoCuentaPagar.PARCIAL]).select_related("proveedor")
    total = vencido = 0
    por_proveedor = {}
    for c in abiertas:
        total += c.saldo
        fila = por_proveedor.setdefault(c.proveedor_id, {"proveedor": c.proveedor_id, "nombre": c.proveedor.nombre,
                                                         "saldo": 0, "vencido": 0, "cuentas": 0})
        fila["saldo"] += c.saldo
        fila["cuentas"] += 1
        if c.vencimiento < fecha:
            vencido += c.saldo
            fila["vencido"] += c.saldo
    inicio = fecha.replace(day=1)
    comprado = (Compra.objects.filter(estado_compra=EstadoCompra.CONFIRMADA, fecha__gte=inicio, fecha__lte=fecha)
                .aggregate(t=Sum("total"))["t"] or 0)
    pagado = Pago.objects.filter(anulado=False, fecha__gte=inicio, fecha__lte=fecha).aggregate(t=Sum("monto"))["t"] or 0
    return {"fecha": fecha, "total_por_pagar": total, "vencido": vencido, "comprado_mes": comprado,
            "pagado_mes": pagado, "por_proveedor": sorted(por_proveedor.values(), key=lambda f: -f["saldo"])}
