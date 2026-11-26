"""Reglas de ventas: precios, stock vendible, registro de la venta, entrega, cobros y anulación.

Una venta registrada ya está confirmada: en la misma transacción se valida el stock, se descuenta
del inventario lote por lote y nace su cuenta por cobrar. Si algo falla, no queda nada a medias.
"""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection, transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from apps.core import auditoria
from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.inventario import servicios as inventario
from apps.inventario.models import Item, Motivo, TipoMovimiento, Unidad
from apps.leche import servicios as leche
from apps.leche.models import DestinoLeche, LoteLeche, TipoDestino
from apps.queso.models import LoteQueso
from apps.queso.servicios import _queso_en_inventario

from .models import (
    DIAS_CREDITO, UNIDAD_PRODUCTO, Cliente, Cobro, CuentaPorCobrar, EstadoCuenta, EstadoVenta, Precio, Producto,
    Venta, VentaLote,
)

CERO = Decimal("0")
# Leche cruda: solo se vende la de los últimos días.
DIAS_LECHE_VENDIBLE = 3
PERMISO_PRECIOS = "ventas.precio.gestionar"
PERMISO_ANULAR = "ventas.venta.aprobar"
_CANDADO_NUMERO = 7_340_022


def hoy():
    return leche.hoy()


# --- Precios ---------------------------------------------------------------------------------

def precio_para(tipo_cliente: str, producto: str, cantidad: Decimal) -> tuple[int, Precio]:
    """El precio más conveniente entre las filas que aplican: la base, la del tipo de cliente y las
    de volumen cuya cantidad mínima se alcanza."""
    filas = Precio.objects.filter(
        activo=True, producto=producto, cantidad_minima__lte=cantidad,
    ).filter(Q(tipo_cliente="") | Q(tipo_cliente=tipo_cliente)).order_by("precio_unitario", "-cantidad_minima")
    fila = filas.first()
    if fila is None:
        raise ReglaNegocio(f"No hay precio cargado para {Producto(producto).label.lower()}. Pedile al Administrador que lo cargue.")
    return fila.precio_unitario, fila


def calcular_total(cantidad: Decimal, precio: int) -> int:
    return int((Decimal(cantidad) * precio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# --- Stock vendible --------------------------------------------------------------------------

def stock_queso_vendible(fecha=None) -> list[dict]:
    """Lotes de queso aprobados con kg en stock, del más viejo al más nuevo (así sale primero lo más viejo).
    Con fecha, solo los elaborados hasta ese día (una venta no puede salir de un lote posterior)."""
    filas = []
    lotes = LoteQueso.objects.filter(estado=EstadoRegistro.APROBADO)
    if fecha is not None:
        lotes = lotes.filter(fecha__lte=fecha)
    for lote in lotes.order_by("fecha", "numero"):
        kg = _queso_en_inventario(lote)
        if kg > 0:
            filas.append({"lote": lote, "id": lote.pk, "codigo": lote.codigo, "fecha": lote.fecha, "disponible": kg})
    return filas


def _destinos_venta_libres(lote_leche):
    return DestinoLeche.objects.filter(lote=lote_leche, tipo=TipoDestino.VENTA, uso_venta__isnull=True).order_by("fecha_creacion")


def leche_vendible(lote_leche: LoteLeche) -> Decimal:
    destinada = _destinos_venta_libres(lote_leche).aggregate(t=Sum("litros"))["t"] or CERO
    saldo = lote_leche.saldo_disponible if lote_leche.estado in leche.ESTADOS_CON_DESTINOS else CERO
    return destinada + saldo


def stock_leche_vendible(fecha=None) -> list[dict]:
    fecha = fecha or hoy()
    desde = fecha - datetime.timedelta(days=DIAS_LECHE_VENDIBLE - 1)
    filas = []
    for lote in leche.con_totales(leche.lotes_validos().filter(fecha__gte=desde, fecha__lte=fecha)).order_by("fecha", "ordene"):
        litros = leche_vendible(lote)
        if litros > 0:
            filas.append({"lote": lote, "id": lote.pk, "codigo": lote.codigo, "fecha": lote.fecha, "disponible": litros})
    return filas


def stock_vendible(producto: str, fecha=None) -> list[dict]:
    return stock_queso_vendible(fecha) if producto == Producto.QUESO else stock_leche_vendible(fecha)


def _formato(cantidad, producto) -> str:
    unidad = "kg" if producto == Producto.QUESO else "L"
    return f"{Decimal(cantidad).normalize():f}".replace(".", ",") + f" {unidad}"


def _asignar_lotes(producto, cantidad, lotes_pedidos, fecha) -> list[tuple[dict, Decimal]]:
    """Reparte la cantidad entre lotes: los que eligió el usuario o, si no eligió, del más viejo al más nuevo."""
    disponibles = stock_vendible(producto, fecha)
    total = sum((d["disponible"] for d in disponibles), CERO)
    if cantidad > total:
        raise ReglaNegocio(
            f"No hay stock suficiente: hay {_formato(total, producto)} disponibles para vender "
            f"y se pidieron {_formato(cantidad, producto)}."
        )
    por_id = {str(d["id"]): d for d in disponibles}
    asignacion = []
    if lotes_pedidos:
        suma = CERO
        for pedido in lotes_pedidos:
            d = por_id.get(str(pedido["lote"]))
            pedida = Decimal(pedido["cantidad"])
            if d is None:
                raise ReglaNegocio("Uno de los lotes elegidos no tiene stock para vender.")
            if pedida <= 0 or pedida > d["disponible"]:
                raise ReglaNegocio(f"El lote {d['codigo']} tiene {_formato(d['disponible'], producto)} disponibles.")
            asignacion.append((d, pedida))
            suma += pedida
        if suma != cantidad:
            raise ReglaNegocio("Lo asignado a los lotes no suma la cantidad vendida.")
        return asignacion
    restante = cantidad
    for d in disponibles:
        if restante <= 0:
            break
        tomar = min(restante, d["disponible"])
        asignacion.append((d, tomar))
        restante -= tomar
    return asignacion


def _descontar_queso(usuario, venta, lote: LoteQueso, cantidad: Decimal):
    lote = LoteQueso.objects.select_for_update().get(pk=lote.pk)
    disponible = _queso_en_inventario(lote)
    if lote.estado != EstadoRegistro.APROBADO or cantidad > disponible:
        raise ReglaNegocio(f"El lote {lote.codigo} ya no tiene ese stock. Volvé a cargar la venta.")
    VentaLote.objects.create(venta=venta, lote_queso=lote, cantidad=cantidad)
    inventario.registrar(usuario, item=Item.QUESO, tipo=TipoMovimiento.SALIDA, motivo=Motivo.VENTA,
                         cantidad=cantidad, unidad=Unidad.KG, lote_queso=lote, venta=venta,
                         nota=f"{venta.codigo} · {venta.cliente.nombre}")


def _descontar_leche(usuario, venta, lote: LoteLeche, litros: Decimal):
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if litros > leche_vendible(lote):
        raise ReglaNegocio(f"El lote {lote.codigo} ya no tiene esos litros. Volvé a cargar la venta.")
    restante = litros
    # Primero la leche que ya estaba destinada a venta; después el saldo sin destino.
    for destino in _destinos_venta_libres(lote):
        if restante <= 0:
            break
        if destino.litros > restante:
            destino.litros -= restante
            destino.save(update_fields=["litros"])
            destino = DestinoLeche.objects.create(lote=lote, tipo=TipoDestino.VENTA, litros=restante,
                                                  nota=venta.codigo, creado_por=usuario)
        VentaLote.objects.create(venta=venta, lote_leche=lote, destino=destino, cantidad=destino.litros)
        restante -= destino.litros
    if restante > 0:
        destino = leche.asignar_destino(usuario, lote, tipo=TipoDestino.VENTA, litros=restante, nota=venta.codigo)
        VentaLote.objects.create(venta=venta, lote_leche=lote, destino=destino, cantidad=restante)
    inventario.registrar(usuario, item=Item.LECHE, tipo=TipoMovimiento.SALIDA, motivo=Motivo.VENTA,
                         cantidad=litros, unidad=Unidad.L, lote_leche=lote, venta=venta,
                         nota=f"{venta.codigo} · {venta.cliente.nombre}")


def _siguiente_numero() -> int:
    with connection.cursor() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", [_CANDADO_NUMERO])
    return (Venta.objects.aggregate(m=Max("numero"))["m"] or 0) + 1


# --- Registrar -------------------------------------------------------------------------------

@transaction.atomic
def registrar_venta(usuario, *, cliente, producto: str, cantidad, fecha=None, precio_unitario=None,
                    lotes=None, entregada: bool = False, cobrar_ahora: bool = False, medio: str = "efectivo",
                    observaciones: str = "", id=None) -> tuple[Venta, bool]:
    if id is not None and (existente := Venta.objects.filter(pk=id).first()):
        return existente, False
    cliente = cliente if isinstance(cliente, Cliente) else Cliente.objects.filter(pk=cliente).first()
    if cliente is None or not cliente.activo or cliente.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El cliente no existe o está dado de baja.")
    fecha = fecha or hoy()
    if fecha > hoy():
        raise ReglaNegocio("No se puede registrar una venta con fecha futura.")
    cantidad = Decimal(cantidad)
    if cantidad <= 0:
        raise ReglaNegocio("La cantidad tiene que ser mayor a cero.")

    lista, _ = precio_para(cliente.tipo, producto, cantidad)
    precio = lista if precio_unitario in (None, "") else int(precio_unitario)
    if precio != lista and not usuario.tiene_permiso(PERMISO_PRECIOS):
        raise ReglaNegocio("Solo el Administrador puede cambiar el precio de lista.")
    if precio <= 0:
        raise ReglaNegocio("El precio tiene que ser mayor a cero.")

    asignacion = _asignar_lotes(producto, cantidad, lotes, fecha)
    venta = Venta(numero=_siguiente_numero(), fecha=fecha, cliente=cliente, producto=producto, cantidad=cantidad,
                  precio_unitario=precio, precio_de_lista=lista, total=calcular_total(cantidad, precio),
                  observaciones=observaciones)
    if id is not None:
        venta.id = id
    venta.save()

    for d, parte in asignacion:
        if producto == Producto.QUESO:
            _descontar_queso(usuario, venta, d["lote"], parte)
        else:
            _descontar_leche(usuario, venta, d["lote"], parte)

    cuenta = CuentaPorCobrar.objects.create(
        venta=venta, cliente=cliente, monto=venta.total, fecha_emision=fecha,
        vencimiento=fecha + datetime.timedelta(days=DIAS_CREDITO[cliente.condicion_pago]),
    )
    auditoria.registrar("registrar_venta", "ventas", venta.pk, cambios={
        "cliente": cliente.nombre, "producto": producto, "cantidad": cantidad, "precio_unitario": precio,
        "precio_de_lista": lista, "total": venta.total,
        "lotes": {d["codigo"]: parte for d, parte in asignacion}, "vencimiento": cuenta.vencimiento,
    })
    if entregada:
        entregar(usuario, venta)
    if cobrar_ahora:
        registrar_cobro(usuario, cuenta, monto=venta.total, fecha=fecha, medio=medio)
    return Venta.objects.get(pk=venta.pk), True


def _actualizar_estado(venta: Venta) -> None:
    cuenta = CuentaPorCobrar.objects.get(venta=venta)
    if venta.estado_venta == EstadoVenta.ANULADA:
        return
    nuevo = EstadoVenta.PENDIENTE
    if venta.fecha_entrega:
        nuevo = EstadoVenta.COBRADA if cuenta.saldo == 0 else EstadoVenta.ENTREGADA
    if nuevo != venta.estado_venta:
        venta.estado_venta = nuevo
        venta.save()


@transaction.atomic
def entregar(usuario, venta: Venta) -> Venta:
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.estado_venta == EstadoVenta.ANULADA:
        raise ReglaNegocio("La venta está anulada.")
    if venta.fecha_entrega:
        raise ReglaNegocio("La venta ya figura como entregada.")
    venta.fecha_entrega = timezone.now()
    venta.save()
    auditoria.registrar("entregar", "ventas", venta.pk)
    _actualizar_estado(venta)
    return venta


# --- Cobros ----------------------------------------------------------------------------------

def _recalcular_cuenta(cuenta: CuentaPorCobrar) -> None:
    cobrado = cuenta.cobros.filter(anulado=False).aggregate(t=Sum("monto"))["t"] or 0
    cuenta.cobrado = cobrado
    if cuenta.estado != EstadoCuenta.ANULADA:
        cuenta.estado = (EstadoCuenta.COBRADA if cobrado >= cuenta.monto
                         else EstadoCuenta.PARCIAL if cobrado else EstadoCuenta.PENDIENTE)
    cuenta.save(update_fields=["cobrado", "estado"])


@transaction.atomic
def registrar_cobro(usuario, cuenta: CuentaPorCobrar, *, monto, fecha=None, medio="efectivo", referencia="") -> Cobro:
    cuenta = CuentaPorCobrar.objects.select_for_update().get(pk=cuenta.pk)
    if cuenta.estado == EstadoCuenta.ANULADA:
        raise ReglaNegocio("La cuenta está anulada.")
    monto = int(monto)
    if monto <= 0:
        raise ReglaNegocio("El monto tiene que ser mayor a cero.")
    if monto > cuenta.saldo:
        raise ReglaNegocio(f"El saldo de la cuenta es Gs. {cuenta.saldo:,}".replace(",", ".") + ": no se puede cobrar más.")
    fecha = fecha or hoy()
    if fecha > hoy():
        raise ReglaNegocio("No se puede registrar un cobro con fecha futura.")
    cobro = Cobro.objects.create(cuenta=cuenta, fecha=fecha, monto=monto, medio=medio, referencia=referencia,
                                 usuario=usuario)
    _recalcular_cuenta(cuenta)
    auditoria.registrar("registrar_cobro", "cuentas_por_cobrar", cuenta.pk, cambios={
        "venta": cuenta.venta.codigo, "monto": monto, "medio": medio, "saldo": [cuenta.saldo + monto, cuenta.saldo]})
    _actualizar_estado(cuenta.venta)
    return cobro


@transaction.atomic
def anular_cobro(usuario, cobro: Cobro, motivo: str) -> Cobro:
    if not usuario.tiene_permiso(PERMISO_ANULAR):
        raise ReglaNegocio("Solo el Administrador anula cobros.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para anular un cobro hace falta el motivo.")
    cobro = Cobro.objects.select_for_update().get(pk=cobro.pk)
    if cobro.anulado:
        raise ReglaNegocio("El cobro ya está anulado.")
    cobro.anulado, cobro.motivo_anulacion = True, motivo
    cobro.save(update_fields=["anulado", "motivo_anulacion"])
    _recalcular_cuenta(cobro.cuenta)
    auditoria.registrar("anular_cobro", "cuentas_por_cobrar", cobro.cuenta_id,
                        cambios={"cobro": cobro.pk, "monto": cobro.monto}, motivo=motivo)
    venta = cobro.cuenta.venta
    if venta.estado_venta == EstadoVenta.COBRADA:
        venta.estado_venta = EstadoVenta.ENTREGADA
        venta.save()
    return cobro


# --- Anular venta ----------------------------------------------------------------------------

@transaction.atomic
def anular_venta(usuario, venta: Venta, motivo: str) -> Venta:
    """Devuelve el stock a sus lotes y anula la cuenta. Antes hay que anular los cobros."""
    if not usuario.tiene_permiso(PERMISO_ANULAR):
        raise ReglaNegocio("Solo el Administrador anula ventas.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para anular una venta hace falta el motivo.")
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.estado_venta == EstadoVenta.ANULADA:
        raise ReglaNegocio("La venta ya está anulada.")
    cuenta = venta.cuenta
    if cuenta.cobros.filter(anulado=False).exists():
        raise ReglaNegocio("La venta tiene cobros registrados: anulalos primero.")
    for vl in venta.lotes.select_related("lote_queso", "lote_leche"):
        if vl.lote_queso_id:
            inventario.registrar(usuario, item=Item.QUESO, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.DEVOLUCION,
                                 cantidad=vl.cantidad, unidad=Unidad.KG, lote_queso=vl.lote_queso, venta=venta)
        else:
            inventario.registrar(usuario, item=Item.LECHE, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.DEVOLUCION,
                                 cantidad=vl.cantidad, unidad=Unidad.L, lote_leche=vl.lote_leche, venta=venta)
            vl.destino = None  # los litros vuelven a quedar destinados a venta, libres
            vl.save(update_fields=["destino"])
    cuenta.estado = EstadoCuenta.ANULADA
    cuenta.save(update_fields=["estado"])
    venta.estado_venta = EstadoVenta.ANULADA
    venta.save()
    venta.anular(motivo)
    return venta


# --- Consultas -------------------------------------------------------------------------------

def ventas_validas():
    return Venta.objects.exclude(estado_venta=EstadoVenta.ANULADA)


def clientes_de_lote_queso(lote: LoteQueso) -> list[dict]:
    """Trazabilidad hacia el cliente: a quién se vendió cada kg de un lote de queso."""
    filas = (VentaLote.objects.filter(lote_queso=lote).exclude(venta__estado_venta=EstadoVenta.ANULADA)
             .select_related("venta__cliente").order_by("venta__fecha", "venta__numero"))
    return [{"cliente": f.venta.cliente_id, "nombre": f.venta.cliente.nombre, "venta": f.venta_id,
             "codigo_venta": f.venta.codigo, "fecha": f.venta.fecha, "kg": f.cantidad} for f in filas]


def historial_cliente(cliente: Cliente) -> dict:
    ventas = (Venta.objects.filter(cliente=cliente).select_related("cuenta")
              .prefetch_related("lotes__lote_queso", "lotes__lote_leche").order_by("-fecha", "-numero"))
    lotes = {}
    for vl in VentaLote.objects.filter(venta__cliente=cliente).exclude(venta__estado_venta=EstadoVenta.ANULADA) \
            .select_related("lote_queso", "lote_leche", "venta"):
        origen = vl.lote_queso or vl.lote_leche
        clave = str(origen.pk)
        fila = lotes.setdefault(clave, {
            "tipo": "queso" if vl.lote_queso_id else "leche", "lote": origen.pk, "codigo": origen.codigo,
            "fecha_lote": origen.fecha, "cantidad": CERO, "unidad": "kg" if vl.lote_queso_id else "l", "ventas": [],
        })
        fila["cantidad"] += vl.cantidad
        if vl.venta.codigo not in fila["ventas"]:
            fila["ventas"].append(vl.venta.codigo)
    validas = [v for v in ventas if v.estado_venta != EstadoVenta.ANULADA]
    return {
        "ventas": ventas,
        "lotes_entregados": sorted(lotes.values(), key=lambda f: f["fecha_lote"], reverse=True),
        "totales": {
            "compras": len(validas),
            "total_comprado": sum(v.total for v in validas),
            "kg_queso": sum((v.cantidad for v in validas if v.producto == Producto.QUESO), CERO),
            "litros_leche": sum((v.cantidad for v in validas if v.producto == Producto.LECHE), CERO),
            "saldo_pendiente": sum(v.cuenta.saldo for v in validas if v.cuenta.estado != EstadoCuenta.ANULADA),
            "ultima_compra": validas[0].fecha if validas else None,
        },
    }


def resumen_cuentas(fecha=None) -> dict:
    fecha = fecha or hoy()
    abiertas = CuentaPorCobrar.objects.filter(estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL]).select_related(
        "cliente", "venta")
    por_cliente = {}
    total = vencido = 0
    for c in abiertas:
        total += c.saldo
        if c.vencimiento < fecha:
            vencido += c.saldo
        fila = por_cliente.setdefault(c.cliente_id, {"cliente": c.cliente_id, "nombre": c.cliente.nombre,
                                                      "saldo": 0, "vencido": 0, "cuentas": 0})
        fila["saldo"] += c.saldo
        fila["cuentas"] += 1
        if c.vencimiento < fecha:
            fila["vencido"] += c.saldo
    inicio_mes = fecha.replace(day=1)
    cobrado_mes = Cobro.objects.filter(anulado=False, fecha__gte=inicio_mes, fecha__lte=fecha).aggregate(t=Sum("monto"))["t"] or 0
    vendido_mes = ventas_validas().filter(fecha__gte=inicio_mes, fecha__lte=fecha).aggregate(t=Sum("total"))["t"] or 0
    return {
        "fecha": fecha, "total_por_cobrar": total, "vencido": vencido,
        "vendido_mes": vendido_mes, "cobrado_mes": cobrado_mes,
        "por_cliente": sorted(por_cliente.values(), key=lambda f: -f["saldo"]),
    }
