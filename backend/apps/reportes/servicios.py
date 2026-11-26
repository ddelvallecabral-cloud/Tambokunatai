"""Números del tablero y de los reportes. Todo sale de los registros cargados; acá no se guarda nada.

Reglas de cálculo (ver DESIGN.md, Fase 6):
- Ingresos: ventas no anuladas, por la fecha de la venta (lo vendido, se haya cobrado o no).
- Gastos: solo los aprobados, por la fecha del gasto. Los pendientes se informan aparte.
- Compras de insumos: en el estado de resultados cuentan en el mes en que se compran (decisión del dueño).
- Costo de la leche por litro: gastos aprobados del centro "Producción de leche" del mes ÷ litros ordeñados ese mes.
- Costo de un lote de queso: litros × costo por litro del mes + insumos consumidos (al precio promedio de compra)
  + su parte de los gastos del centro "Elaboración de queso" del mes (repartidos por litros procesados).
- Flujo de caja: entradas = cobros; salidas = pagos a proveedores + gastos aprobados (se toman como pagados en su fecha).
"""

import calendar
import datetime
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.compras.models import Compra, CompraItem, CuentaPorPagar, EstadoCompra, EstadoCuentaPagar, Pago
from apps.core.mixins import EstadoRegistro
from apps.core.models import Auditoria
from apps.gastos.models import CentroCosto, Gasto
from apps.leche.models import LoteLeche
from apps.queso.models import LoteQueso
from apps.ventas.models import UNIDAD_PRODUCTO, Cobro, CuentaPorCobrar, EstadoCuenta, EstadoVenta, Producto, Venta, VentaLote

from . import alertas as config_alertas

CERO = Decimal("0")
NOMBRE_PRODUCTO = {"leche": "Leche", "queso": "Queso"}


def hoy() -> datetime.date:
    from apps.leche import servicios as leche

    return leche.hoy()


def gs(valor) -> int:
    """Redondea a guaraníes enteros."""
    return int(Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def texto_gs(valor) -> str:
    return "Gs. " + f"{int(valor):,}".replace(",", ".")


def mes_de(fecha: datetime.date) -> tuple[datetime.date, datetime.date]:
    return fecha.replace(day=1), fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])


def _meses(desde: datetime.date, hasta: datetime.date):
    actual = desde.replace(day=1)
    while actual <= hasta:
        yield actual
        actual = (actual.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def _decimal(valor, lugares=1):
    return DecimalField(max_digits=14, decimal_places=lugares)


# --- Consultas base ---------------------------------------------------------------------------

def lotes_leche_validos():
    return LoteLeche.objects.exclude(estado=EstadoRegistro.ANULADO)


def lotes_queso_cerrados():
    """Lotes con kg cargados (pendientes, aprobados o rechazados). Los en elaboración y los anulados no cuentan."""
    return LoteQueso.objects.exclude(estado__in=[EstadoRegistro.ANULADO, EstadoRegistro.BORRADOR]).filter(
        kg_obtenidos__isnull=False)


def ventas_validas():
    return Venta.objects.exclude(estado_venta=EstadoVenta.ANULADA)


def gastos_aprobados():
    return Gasto.objects.filter(estado=EstadoRegistro.APROBADO)


def compras_confirmadas():
    return Compra.objects.filter(estado_compra=EstadoCompra.CONFIRMADA)


def litros_entre(desde, hasta) -> Decimal:
    return lotes_leche_validos().filter(fecha__gte=desde, fecha__lte=hasta).aggregate(
        t=Coalesce(Sum("litros"), Value(CERO), output_field=_decimal(1)))["t"]


def queso_entre(desde, hasta) -> dict:
    r = lotes_queso_cerrados().filter(fecha__gte=desde, fecha__lte=hasta).aggregate(
        kg=Coalesce(Sum("kg_obtenidos"), Value(CERO), output_field=_decimal(2)),
        merma=Coalesce(Sum("merma_kg"), Value(CERO), output_field=_decimal(2)),
        litros=Coalesce(Sum("litros_leche"), Value(CERO), output_field=_decimal(1)),
        lotes=Count("id"),
    )
    r["rendimiento"] = (r["litros"] / r["kg"]).quantize(Decimal("0.01")) if r["kg"] else None
    return r


def ventas_por_producto(desde, hasta) -> dict:
    filas = ventas_validas().filter(fecha__gte=desde, fecha__lte=hasta).values("producto").annotate(
        total=Sum("total"), cantidad=Sum("cantidad"), ventas=Count("id"))
    datos = {p: {"total": 0, "cantidad": CERO, "ventas": 0} for p in Producto.values}
    for f in filas:
        datos[f["producto"]] = {"total": f["total"] or 0, "cantidad": f["cantidad"] or CERO, "ventas": f["ventas"]}
    return datos


def gastos_por(campo: str, desde, hasta) -> list[dict]:
    filas = gastos_aprobados().filter(fecha__gte=desde, fecha__lte=hasta).values(campo).annotate(
        total=Sum("monto"), cantidad=Count("id")).order_by("-total")
    return [{campo: f[campo], "total": f["total"], "cantidad": f["cantidad"]} for f in filas]


# --- Costos ------------------------------------------------------------------------------------

class Costos:
    """Calcula y recuerda costos por mes y por insumo para no repetir consultas dentro de un reporte."""

    def __init__(self):
        self._litro = {}
        self._queso_mes = {}
        self._insumo = {}

    def litro(self, fecha: datetime.date) -> dict:
        """Costo de producir un litro en el mes de `fecha`."""
        inicio, fin = mes_de(fecha)
        if inicio not in self._litro:
            litros = litros_entre(inicio, fin)
            gastos = gastos_aprobados().filter(fecha__gte=inicio, fecha__lte=fin,
                                               centro_costo=CentroCosto.LECHE).aggregate(t=Sum("monto"))["t"] or 0
            self._litro[inicio] = {"gastos": gastos, "litros": litros,
                                   "por_litro": (Decimal(gastos) / litros) if litros else CERO}
        return self._litro[inicio]

    def elaboracion(self, fecha: datetime.date) -> dict:
        """Gastos del centro "Elaboración de queso" del mes y litros procesados para repartirlos."""
        inicio, fin = mes_de(fecha)
        if inicio not in self._queso_mes:
            litros = lotes_queso_cerrados().filter(fecha__gte=inicio, fecha__lte=fin).aggregate(
                t=Coalesce(Sum("litros_leche"), Value(CERO), output_field=_decimal(1)))["t"]
            gastos = gastos_aprobados().filter(fecha__gte=inicio, fecha__lte=fin,
                                               centro_costo=CentroCosto.QUESO).aggregate(t=Sum("monto"))["t"] or 0
            self._queso_mes[inicio] = {"gastos": gastos, "litros": litros,
                                       "por_litro": (Decimal(gastos) / litros) if litros else CERO}
        return self._queso_mes[inicio]

    def insumo(self, insumo_id, fecha: datetime.date) -> Decimal | None:
        """Precio promedio ponderado de compra hasta `fecha` (si no hay, el de cualquier compra; si nunca se compró, None)."""
        clave = (insumo_id, fecha)
        if clave not in self._insumo:
            base = CompraItem.objects.filter(insumo_id=insumo_id, compra__estado_compra=EstadoCompra.CONFIRMADA)
            r = base.filter(compra__fecha__lte=fecha).aggregate(c=Sum("cantidad"), s=Sum("subtotal"))
            if not r["c"]:
                r = base.aggregate(c=Sum("cantidad"), s=Sum("subtotal"))
            self._insumo[clave] = (Decimal(r["s"]) / r["c"]) if r["c"] else None
        return self._insumo[clave]

    def lote(self, lote: LoteQueso) -> dict:
        litro = self.litro(lote.fecha)
        elab = self.elaboracion(lote.fecha)
        leche = lote.litros_leche * litro["por_litro"]
        insumos = CERO
        sin_precio = []
        for li in lote.insumos.all():
            cantidad = li.cantidad_consumida if li.cantidad_consumida is not None else CERO
            if not cantidad:
                continue
            precio = self.insumo(li.insumo_id, lote.fecha)
            if precio is None:
                sin_precio.append(li.insumo.nombre)
                continue
            insumos += cantidad * precio
        elaboracion = lote.litros_leche * elab["por_litro"]
        total = leche + insumos + elaboracion
        kg = lote.kg_netos or CERO
        return {
            "leche": gs(leche), "insumos": gs(insumos), "elaboracion": gs(elaboracion),
            "total": gs(leche) + gs(insumos) + gs(elaboracion),
            "por_kg": gs(total / kg) if kg else None,
            "insumos_sin_precio": sin_precio,
            "costo_litro": gs(litro["por_litro"]),
        }


def _venta_por_lote(desde=None, hasta=None, producto=None):
    """Reparte el total de cada venta entre los lotes de los que salió (proporcional a la cantidad)."""
    qs = VentaLote.objects.select_related("venta").exclude(venta__estado_venta=EstadoVenta.ANULADA)
    if desde:
        qs = qs.filter(venta__fecha__gte=desde)
    if hasta:
        qs = qs.filter(venta__fecha__lte=hasta)
    if producto:
        qs = qs.filter(venta__producto=producto)
    por_venta = defaultdict(list)
    for vl in qs.order_by("venta_id", "id"):
        por_venta[vl.venta_id].append(vl)
    for filas in por_venta.values():
        venta = filas[0].venta
        resto = venta.total
        for i, vl in enumerate(filas):
            monto = resto if i == len(filas) - 1 else gs(Decimal(venta.total) * vl.cantidad / venta.cantidad)
            resto -= monto
            yield vl, monto


# --- Reportes ----------------------------------------------------------------------------------

def rentabilidad_lotes(desde, hasta) -> dict:
    """Lotes de queso elaborados en el período: costo, lo vendido hasta hoy y el resultado."""
    costos = Costos()
    lotes = list(lotes_queso_cerrados().filter(fecha__gte=desde, fecha__lte=hasta)
                 .prefetch_related("insumos__insumo").order_by("fecha", "numero"))
    vendido = defaultdict(lambda: {"kg": CERO, "ingresos": 0})
    ids = {l.id for l in lotes}
    for vl, monto in _venta_por_lote(producto=Producto.QUESO):
        if vl.lote_queso_id in ids:
            vendido[vl.lote_queso_id]["kg"] += vl.cantidad
            vendido[vl.lote_queso_id]["ingresos"] += monto
    filas = []
    for l in lotes:
        c = costos.lote(l)
        v = vendido[l.id]
        kg = l.kg_netos or CERO
        costo_vendido = gs(Decimal(c["total"]) * v["kg"] / kg) if kg else 0
        filas.append({
            "lote": str(l.id), "codigo": l.codigo, "fecha": l.fecha, "estado": l.estado,
            "litros": l.litros_leche, "kg": kg, "rendimiento": l.rendimiento_l_kg,
            "costo_leche": c["leche"], "costo_insumos": c["insumos"], "costo_elaboracion": c["elaboracion"],
            "costo_total": c["total"], "costo_kg": c["por_kg"],
            "kg_vendidos": v["kg"], "kg_sin_vender": kg - v["kg"], "ingresos": v["ingresos"],
            "precio_promedio_kg": gs(Decimal(v["ingresos"]) / v["kg"]) if v["kg"] else None,
            "costo_de_lo_vendido": costo_vendido,
            "margen_vendido": v["ingresos"] - costo_vendido,
            "resultado": v["ingresos"] - c["total"],
            "insumos_sin_precio": c["insumos_sin_precio"],
        })
    totales = {k: sum(f[k] for f in filas) for k in
               ("costo_leche", "costo_insumos", "costo_elaboracion", "costo_total", "ingresos",
                "costo_de_lo_vendido", "margen_vendido", "resultado")}
    totales["kg"] = sum((f["kg"] for f in filas), CERO)
    totales["kg_vendidos"] = sum((f["kg_vendidos"] for f in filas), CERO)
    return {"desde": desde, "hasta": hasta, "lotes": filas, "totales": totales}


def rentabilidad_productos(desde, hasta) -> dict:
    """Margen bruto por producto: lo vendido en el período menos lo que costó producir eso que se vendió."""
    costos = Costos()
    ventas = ventas_por_producto(desde, hasta)
    costo = {"leche": CERO, "queso": CERO}
    cache_lote = {}
    for vl, _monto in _venta_por_lote(desde, hasta):
        if vl.lote_leche_id:
            costo["leche"] += vl.cantidad * costos.litro(vl.lote_leche.fecha)["por_litro"]
        elif vl.lote_queso_id:
            if vl.lote_queso_id not in cache_lote:
                lote = LoteQueso.objects.prefetch_related("insumos__insumo").get(pk=vl.lote_queso_id)
                c = costos.lote(lote)
                kg = lote.kg_netos or CERO
                cache_lote[vl.lote_queso_id] = (Decimal(c["total"]) / kg) if kg else CERO
            costo["queso"] += vl.cantidad * cache_lote[vl.lote_queso_id]
    productos = []
    for p in ("leche", "queso"):
        ingresos = ventas[p]["total"]
        c = gs(costo[p])
        productos.append({
            "producto": p, "nombre": NOMBRE_PRODUCTO[p], "cantidad": ventas[p]["cantidad"],
            "unidad": "L" if p == "leche" else "kg", "ventas": ventas[p]["ventas"],
            "ingresos": ingresos, "costo": c, "margen": ingresos - c,
            "margen_pct": round((ingresos - c) * 100 / ingresos, 1) if ingresos else None,
            "precio_promedio": gs(Decimal(ingresos) / ventas[p]["cantidad"]) if ventas[p]["cantidad"] else None,
            "costo_unitario": gs(costo[p] / ventas[p]["cantidad"]) if ventas[p]["cantidad"] else None,
        })
    administracion = gastos_aprobados().filter(fecha__gte=desde, fecha__lte=hasta,
                                               centro_costo=CentroCosto.ADMINISTRACION).aggregate(t=Sum("monto"))["t"] or 0
    meses = [{"mes": m, **{k: gs(v) if k == "por_litro" else v for k, v in costos.litro(m).items()}}
             for m in _meses(desde, hasta)]
    return {"desde": desde, "hasta": hasta, "productos": productos,
            "total": {"ingresos": sum(p["ingresos"] for p in productos), "costo": sum(p["costo"] for p in productos),
                      "margen": sum(p["margen"] for p in productos)},
            "gastos_administracion": administracion, "costo_litro_por_mes": meses}


def estado_resultados(desde, hasta) -> dict:
    """Ingresos − gastos − compras de insumos del período."""
    ventas = ventas_por_producto(desde, hasta)
    ingresos = [{"concepto": NOMBRE_PRODUCTO[p], "producto": p, "monto": ventas[p]["total"],
                 "cantidad": ventas[p]["cantidad"]} for p in ("leche", "queso")]
    total_ingresos = sum(i["monto"] for i in ingresos)
    por_categoria = gastos_por("categoria", desde, hasta)
    por_centro = gastos_por("centro_costo", desde, hasta)
    total_gastos = sum(g["total"] for g in por_categoria)
    compras = compras_confirmadas().filter(fecha__gte=desde, fecha__lte=hasta).aggregate(
        t=Sum("total"), n=Count("id"))
    total_compras = compras["t"] or 0
    pendientes = Gasto.objects.filter(estado=EstadoRegistro.PENDIENTE, fecha__gte=desde, fecha__lte=hasta).aggregate(
        t=Sum("monto"), n=Count("id"))
    egresos = total_gastos + total_compras
    return {
        "desde": desde, "hasta": hasta,
        "ingresos": ingresos, "total_ingresos": total_ingresos,
        "gastos_por_categoria": por_categoria, "gastos_por_centro": por_centro, "total_gastos": total_gastos,
        "compras_insumos": total_compras, "cantidad_compras": compras["n"],
        "total_egresos": egresos, "resultado": total_ingresos - egresos,
        "margen_pct": round((total_ingresos - egresos) * 100 / total_ingresos, 1) if total_ingresos else None,
        "gastos_pendientes": {"total": pendientes["t"] or 0, "cantidad": pendientes["n"]},
    }


def flujo_caja(desde, hasta, agrupar: str = "dia") -> dict:
    """Plata que entró (cobros) y salió (pagos a proveedores y gastos aprobados), por día o por mes."""
    clave = (lambda f: f) if agrupar == "dia" else (lambda f: f.replace(day=1))
    filas = defaultdict(lambda: {"cobros": 0, "pagos_proveedores": 0, "gastos": 0})
    for c in Cobro.objects.filter(anulado=False, fecha__gte=desde, fecha__lte=hasta).values("fecha").annotate(t=Sum("monto")):
        filas[clave(c["fecha"])]["cobros"] += c["t"]
    for p in Pago.objects.filter(anulado=False, fecha__gte=desde, fecha__lte=hasta).values("fecha").annotate(t=Sum("monto")):
        filas[clave(p["fecha"])]["pagos_proveedores"] += p["t"]
    for g in gastos_aprobados().filter(fecha__gte=desde, fecha__lte=hasta).values("fecha").annotate(t=Sum("monto")):
        filas[clave(g["fecha"])]["gastos"] += g["t"]
    salida = []
    acumulado = 0
    for periodo in sorted(filas):
        f = filas[periodo]
        neto = f["cobros"] - f["pagos_proveedores"] - f["gastos"]
        acumulado += neto
        salida.append({"periodo": periodo, **f, "salidas": f["pagos_proveedores"] + f["gastos"],
                       "neto": neto, "acumulado": acumulado})
    totales = {k: sum(f[k] for f in salida) for k in ("cobros", "pagos_proveedores", "gastos", "salidas", "neto")}
    return {"desde": desde, "hasta": hasta, "agrupar": agrupar, "filas": salida, "totales": totales}


def cuentas_pendientes(fecha=None) -> dict:
    fecha = fecha or hoy()
    cobrar = CuentaPorCobrar.objects.filter(estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL])
    pagar = CuentaPorPagar.objects.filter(estado__in=[EstadoCuentaPagar.PENDIENTE, EstadoCuentaPagar.PARCIAL])

    def resumir(qs, pagado):
        total = vencido = cantidad = vencidas = 0
        for c in qs.values("monto", pagado, "vencimiento"):
            saldo = c["monto"] - c[pagado]
            total += saldo
            cantidad += 1
            if c["vencimiento"] < fecha:
                vencido += saldo
                vencidas += 1
        return {"total": total, "vencido": vencido, "cuentas": cantidad, "vencidas": vencidas}

    return {"por_cobrar": resumir(cobrar, "cobrado"), "por_pagar": resumir(pagar, "pagado")}


# --- Tablero -----------------------------------------------------------------------------------

def tablero_operativo(fecha=None) -> dict:
    fecha = fecha or hoy()
    inicio, _ = mes_de(fecha)
    dias = []
    for i in range(29, -1, -1):
        d = fecha - datetime.timedelta(days=i)
        dias.append(d)
    por_dia = dict(lotes_leche_validos().filter(fecha__gte=dias[0], fecha__lte=fecha).values("fecha")
                   .annotate(t=Sum("litros")).values_list("fecha", "t"))
    queso_mes = queso_entre(inicio, fecha)
    queso_hoy = queso_entre(fecha, fecha)
    return {
        "fecha": fecha,
        "leche": {"hoy": litros_entre(fecha, fecha), "mes": litros_entre(inicio, fecha),
                  "ultimos_30": [{"fecha": d, "litros": por_dia.get(d, CERO)} for d in dias]},
        "queso": {"hoy_kg": queso_hoy["kg"], "mes_kg": queso_mes["kg"], "mes_merma": queso_mes["merma"],
                  "mes_lotes": queso_mes["lotes"], "mes_litros": queso_mes["litros"],
                  "rendimiento_mes": queso_mes["rendimiento"]},
    }


def tablero_financiero(fecha=None) -> dict:
    fecha = fecha or hoy()
    inicio, _ = mes_de(fecha)
    resultados = estado_resultados(inicio, fecha)
    productos = rentabilidad_productos(inicio, fecha)
    return {
        "ingresos_mes": {i["producto"]: i["monto"] for i in resultados["ingresos"]} | {"total": resultados["total_ingresos"]},
        "gastos_mes": {"por_categoria": resultados["gastos_por_categoria"], "por_centro": resultados["gastos_por_centro"],
                       "total": resultados["total_gastos"], "pendientes": resultados["gastos_pendientes"]},
        "compras_mes": resultados["compras_insumos"],
        "resultado_mes": resultados["resultado"],
        "margen_productos": productos["productos"],
        "cuentas": cuentas_pendientes(fecha),
    }


# --- Alertas -----------------------------------------------------------------------------------

def calcular_alertas(fecha=None, financieras: bool = True) -> list[dict]:
    from apps.inventario.servicios import con_stock
    from apps.leche.models import Ordene

    fecha = fecha or hoy()
    conf = config_alertas.leer()
    salida = []

    p = conf["produccion_baja"]
    if p["activa"] and p["litros_minimos"] > 0:
        minimo = Decimal(str(p["litros_minimos"]))
        desde = fecha - datetime.timedelta(days=6)
        dias = lotes_leche_validos().filter(fecha__gte=desde, fecha__lte=fecha).values("fecha").annotate(
            t=Sum("litros"), n=Count("ordene", distinct=True))
        cargados = {d["fecha"]: d for d in dias}
        for i in range(6, -1, -1):
            d = fecha - datetime.timedelta(days=i)
            fila = cargados.get(d)
            completo = fila and fila["n"] >= len(Ordene.values)
            if d == fecha and not completo:
                continue  # hoy todavía se puede estar cargando
            litros = fila["t"] if fila else CERO
            if litros < minimo:
                texto = (f"{d:%d/%m}: se ordeñaron {litros:.0f} L, menos que el mínimo de {minimo:.0f} L." if litros
                         else f"{d:%d/%m}: no hay ordeñe cargado (mínimo esperado {minimo:.0f} L).")
                salida.append({"tipo": "produccion_baja", "nivel": "alerta", "fecha": d, "texto": texto,
                               "ruta": f"/leche/lotes?desde={d}&hasta={d}"})

    r = conf["rendimiento"]
    if r["activa"]:
        mn, mx = Decimal(str(r["minimo"])), Decimal(str(r["maximo"]))
        for l in lotes_queso_cerrados().filter(fecha__gte=fecha - datetime.timedelta(days=30), fecha__lte=fecha,
                                               rendimiento_l_kg__isnull=False).order_by("-fecha"):
            if not (mn <= l.rendimiento_l_kg <= mx):
                salida.append({"tipo": "rendimiento", "nivel": "alerta", "fecha": l.fecha,
                               "texto": f"Lote {l.codigo}: {l.rendimiento_l_kg:g} L/kg, fuera del rango {mn:g}–{mx:g} L/kg.",
                               "ruta": f"/queso/{l.id}"})

    if conf["stock_bajo"]["activa"]:
        for i in con_stock().filter(activo=True, bajo_minimo=True).order_by("nombre"):
            salida.append({"tipo": "stock_bajo", "nivel": "alerta", "fecha": fecha,
                           "texto": f"{i.nombre}: quedan {i.stock:g} {i.unidad} (mínimo {i.stock_minimo:g}).",
                           "ruta": "/inventario"})

    c = conf["cuentas_vencidas"]
    if financieras and c["activa"]:
        limite = fecha - datetime.timedelta(days=int(c["dias_gracia"]))
        vencidas = CuentaPorCobrar.objects.filter(estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL],
                                                  vencimiento__lt=limite).select_related("cliente", "venta")
        for cta in vencidas.order_by("vencimiento"):
            dias = (fecha - cta.vencimiento).days
            salida.append({"tipo": "cuenta_vencida", "nivel": "alerta", "fecha": cta.vencimiento,
                           "texto": f"{cta.cliente.nombre} debe {texto_gs(cta.saldo)} de {cta.venta.codigo}, vencida hace {dias} "
                                    f"{'día' if dias == 1 else 'días'}.",
                           "ruta": f"/ventas/{cta.venta_id}"})
    return salida


# --- Control y auditoría -----------------------------------------------------------------------

ACCIONES_APROBACION = {"aprobar": "Aprobó", "rechazar": "Rechazó"}
ACCIONES_CONTROL = {
    "editar_bloqueado": "Editó un registro cerrado",
    "aplicar_correccion": "Aplicó una corrección",
    "reabrir": "Reabrió",
    "anular": "Anuló",
    "anular_cobro": "Anuló un cobro",
    "anular_pago": "Anuló un pago",
}
NOMBRE_ENTIDAD = {
    "lotes_leche": "Lote de leche", "lotes_queso": "Lote de queso", "gastos": "Gasto", "ventas": "Venta",
    "compras": "Compra", "cuentas_por_cobrar": "Cuenta por cobrar", "cuentas_por_pagar": "Cuenta por pagar",
    "insumos": "Insumo", "clientes": "Cliente", "proveedores": "Proveedor", "animales": "Animal",
}


def _describir(filas: list[Auditoria]) -> dict:
    """Arma una etiqueta legible y la ruta de pantalla de cada registro mencionado."""
    por_entidad = defaultdict(set)
    for f in filas:
        if f.entidad_id:
            por_entidad[f.entidad].add(f.entidad_id)
    etiquetas = {}

    def cargar(entidad, modelo, etiqueta, ruta, relacionados=()):
        ids = por_entidad.get(entidad)
        if not ids:
            return
        for obj in modelo.objects.filter(pk__in=ids).select_related(*relacionados):
            etiquetas[(entidad, str(obj.pk))] = (etiqueta(obj), ruta(obj))

    cargar("lotes_leche", LoteLeche, lambda o: f"{o.codigo} · {o.litros:g} L", lambda o: f"/leche/lotes/{o.pk}")
    cargar("lotes_queso", LoteQueso, lambda o: o.codigo, lambda o: f"/queso/{o.pk}")
    cargar("gastos", Gasto, lambda o: f"{o.descripcion} · {texto_gs(o.monto)}", lambda o: f"/gastos/{o.pk}")
    cargar("ventas", Venta, lambda o: f"{o.codigo} · {o.cliente.nombre}", lambda o: f"/ventas/{o.pk}", ("cliente",))
    cargar("compras", Compra, lambda o: f"{o.codigo} · {o.proveedor.nombre}", lambda o: f"/compras/{o.pk}", ("proveedor",))
    cargar("cuentas_por_cobrar", CuentaPorCobrar, lambda o: f"Cuenta de {o.venta.codigo} · {o.cliente.nombre}",
           lambda o: f"/ventas/{o.venta_id}", ("venta", "cliente"))
    cargar("cuentas_por_pagar", CuentaPorPagar, lambda o: f"Cuenta de {o.compra.codigo} · {o.proveedor.nombre}",
           lambda o: f"/compras/{o.compra_id}", ("compra", "proveedor"))
    return etiquetas


def _fila_auditoria(f: Auditoria, etiquetas: dict, nombres: dict) -> dict:
    etiqueta, ruta = etiquetas.get((f.entidad, f.entidad_id), (f.entidad_id, None))
    return {
        "id": f.id, "fecha": f.fecha, "usuario": f.usuario.nombre if f.usuario else "Sistema",
        "accion": f.accion, "accion_nombre": nombres.get(f.accion, f.accion),
        "entidad": f.entidad, "entidad_nombre": NOMBRE_ENTIDAD.get(f.entidad, f.entidad),
        "registro": etiqueta, "ruta": ruta, "motivo": f.motivo, "cambios": f.cambios,
    }


def historial_aprobaciones(desde, hasta, usuario=None, entidad=None) -> list[dict]:
    """Quién aprobó o rechazó qué y cuándo (por la fecha de la decisión)."""
    qs = Auditoria.objects.select_related("usuario").filter(
        accion__in=ACCIONES_APROBACION, fecha__date__gte=desde, fecha__date__lte=hasta)
    if usuario:
        qs = qs.filter(usuario_id=usuario)
    if entidad:
        qs = qs.filter(entidad=entidad)
    filas = list(qs.order_by("-fecha"))
    etiquetas = _describir(filas)
    # Un gasto que no supera el monto se aprueba solo al cargarlo: la auditoría lo registra a nombre de
    # quien lo cargó, pero acá se muestra como aprobación automática para no confundir.
    automaticos = set(Gasto.objects.filter(
        pk__in=[f.entidad_id for f in filas if f.entidad == "gastos"], aprobacion_automatica=True,
    ).values_list("pk", flat=True))
    salida = []
    for f in filas:
        fila = _fila_auditoria(f, etiquetas, ACCIONES_APROBACION)
        if f.entidad == "gastos" and f.accion == "aprobar" and f.motivo.startswith("Aprobado automáticamente") \
                and any(str(pk) == f.entidad_id for pk in automaticos):
            if usuario:
                continue
            fila["accion_nombre"] = "Aprobó automáticamente"
            fila["usuario"] = f"Automática (cargó {fila['usuario']})"
        salida.append(fila)
    return salida


def registros_editados(desde=None, hasta=None, solo_sin_revisar: bool = False) -> list[dict]:
    """Cambios sobre registros que ya estaban cerrados o aprobados (para que el dueño los audite)."""
    filtro = Q(accion__in=["editar_bloqueado", "aplicar_correccion", "reabrir", "anular_cobro", "anular_pago"]) | Q(
        accion="anular", cambios__estado__0__in=[EstadoRegistro.APROBADO, EstadoRegistro.CERRADO])
    qs = Auditoria.objects.select_related("usuario", "revision__revisado_por").filter(filtro)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)
    if solo_sin_revisar:
        qs = qs.filter(revision__isnull=True)
    filas = list(qs.order_by("-fecha")[:300])
    etiquetas = _describir(filas)
    salida = []
    for f in filas:
        fila = _fila_auditoria(f, etiquetas, ACCIONES_CONTROL)
        rev = getattr(f, "revision", None)
        fila["revisado"] = {"por": rev.revisado_por.nombre, "fecha": rev.fecha, "nota": rev.nota} if rev else None
        salida.append(fila)
    return salida


def marcar_revisado(usuario, auditoria_id: int, nota: str = ""):
    from apps.core import auditoria
    from apps.core.mixins import ReglaNegocio

    from .models import RevisionRegistro

    fila = Auditoria.objects.filter(pk=auditoria_id).first()
    if fila is None:
        raise ReglaNegocio("No existe ese registro de auditoría.")
    rev, creada = RevisionRegistro.objects.get_or_create(auditoria=fila, defaults={"revisado_por": usuario, "nota": nota})
    if creada:
        auditoria.registrar("revisar", "auditoria", fila.pk, usuario=usuario, motivo=nota)
    return rev


def pendientes_control() -> dict:
    from apps.gastos.servicios import pendientes_de_aprobacion

    return pendientes_de_aprobacion() | {
        "registros_editados": len(registros_editados(solo_sin_revisar=True)),
    }


# --- Mis ventas (rol Ventas) ---------------------------------------------------------------------

def mis_ventas(usuario, desde, hasta, fecha=None) -> dict:
    """Lo que vendió y cobró un vendedor en el período, y lo que le queda por cobrar de sus ventas."""
    fecha = fecha or hoy()
    propias = ventas_validas().filter(creado_por=usuario, fecha__gte=desde, fecha__lte=hasta)
    por_producto = []
    for p in Producto:
        fila = propias.filter(producto=p.value).aggregate(total=Sum("total"), cantidad=Sum("cantidad"), ventas=Count("id"))
        por_producto.append({"producto": p.value, "nombre": p.label, "unidad": UNIDAD_PRODUCTO[p.value],
                             "ventas": fila["ventas"], "cantidad": fila["cantidad"] or CERO, "total": fila["total"] or 0})
    cobrado = Cobro.objects.filter(usuario=usuario, anulado=False, fecha__gte=desde, fecha__lte=hasta) \
        .aggregate(t=Sum("monto"))["t"] or 0
    abiertas = CuentaPorCobrar.objects.filter(venta__creado_por=usuario,
                                              estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL])
    por_cobrar = vencido = 0
    for c in abiertas.values("monto", "cobrado", "vencimiento"):
        saldo = c["monto"] - c["cobrado"]
        por_cobrar += saldo
        if c["vencimiento"] < fecha:
            vencido += saldo
    ventas = [{
        "id": str(v.id), "codigo": v.codigo, "fecha": v.fecha, "cliente": v.cliente.nombre, "producto": v.producto,
        "cantidad": v.cantidad, "unidad": UNIDAD_PRODUCTO[v.producto], "total": v.total,
        "saldo": v.cuenta.saldo if hasattr(v, "cuenta") else 0,
    } for v in propias.select_related("cliente", "cuenta").order_by("-fecha", "-numero")[:100]]
    return {
        "desde": desde, "hasta": hasta, "total": sum(p["total"] for p in por_producto),
        "cantidad_ventas": sum(p["ventas"] for p in por_producto), "por_producto": por_producto,
        "cobrado": cobrado, "por_cobrar": por_cobrar, "vencido": vencido, "ventas": ventas,
    }
