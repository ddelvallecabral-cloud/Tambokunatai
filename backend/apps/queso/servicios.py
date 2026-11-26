"""Elaboración de queso: iniciar, cerrar, aprobar, rechazar, cancelar y trazabilidad.

Flujo:
  1. iniciar: se descuentan los litros de los lotes de leche de origen y se reservan los insumos.
  2. cerrar: con los kg obtenidos se libera la reserva, se descuenta lo consumido de verdad,
     entra el queso al inventario, se calcula el rendimiento y el lote queda pendiente de aprobación.
  3. aprobar / rechazar: solo el Administrador. Rechazado, se corrige y se vuelve a cerrar.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from apps.core import auditoria
from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.core.models import Auditoria
from apps.cuentas.catalogo import ADMIN
from apps.inventario import servicios as inventario
from apps.inventario.models import Insumo, Item, Motivo, MovimientoInventario, TipoMovimiento, Unidad
from apps.leche import servicios as leche
from apps.leche.models import DestinoLeche, LoteLeche, TipoDestino

from .models import CERO, LoteQueso, LoteQuesoInsumo, LoteQuesoLeche

PERMISO_APROBAR = "queso.lote.aprobar"
DIAS_LECHE_DISPONIBLE = 7


def rango_rendimiento() -> tuple[Decimal, Decimal]:
    return (Decimal(str(settings.QUESO_RENDIMIENTO_MIN_L_KG)), Decimal(str(settings.QUESO_RENDIMIENTO_MAX_L_KG)))


# --- Leche disponible para elaborar ----------------------------------------------------------

def _destinos_queso_libres(lote_leche):
    return DestinoLeche.objects.filter(
        lote=lote_leche, tipo=TipoDestino.ELABORACION_QUESO, uso_queso__isnull=True
    ).order_by("fecha_creacion")


def leche_disponible(lote_leche: LoteLeche) -> dict:
    """Litros que un lote de leche todavía puede aportar a un queso:
    los ya destinados a queso sin lote de queso, más el saldo sin destino (si el lote lo permite)."""
    libre_queso = _destinos_queso_libres(lote_leche).aggregate(t=Sum("litros"))["t"] or CERO
    saldo = lote_leche.saldo_disponible if lote_leche.estado in leche.ESTADOS_CON_DESTINOS else CERO
    return {"destinado_a_queso": libre_queso, "sin_destino": saldo, "total": libre_queso + saldo}


def lotes_leche_disponibles(fecha: datetime.date | None = None) -> list[dict]:
    fecha = fecha or leche.hoy()
    desde = fecha - datetime.timedelta(days=DIAS_LECHE_DISPONIBLE - 1)
    filas = []
    lotes = leche.con_totales(leche.lotes_validos().filter(fecha__gte=desde, fecha__lte=fecha)).order_by("fecha", "ordene")
    for lote in lotes:
        disp = leche_disponible(lote)
        if disp["total"] > 0:
            filas.append({"id": lote.pk, "codigo": lote.codigo, "fecha": lote.fecha, "ordene": lote.ordene,
                          "litros": lote.litros, "estado": lote.estado, **disp})
    return filas


def _tomar_leche(usuario, lote_queso: LoteQueso, lote_leche: LoteLeche, litros: Decimal) -> None:
    lote_leche = LoteLeche.objects.select_for_update().get(pk=lote_leche.pk)
    if lote_leche.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio(f"El lote de leche {lote_leche.codigo} está anulado.")
    if lote_leche.fecha > lote_queso.fecha:
        raise ReglaNegocio(f"El lote de leche {lote_leche.codigo} es posterior a la fecha del queso.")
    disponible = leche_disponible(lote_leche)["total"]
    if litros > disponible:
        raise ReglaNegocio(f"{lote_leche.codigo} solo tiene {leche.formato_litros(disponible)} disponibles para queso.")

    restante = litros
    # 1) Primero la leche que ya estaba destinada a queso.
    # El lote de leche ya está bloqueado: nadie más toca sus destinos mientras tanto.
    for destino in _destinos_queso_libres(lote_leche):
        if restante <= 0:
            break
        if destino.litros <= restante:
            LoteQuesoLeche.objects.create(lote_queso=lote_queso, lote_leche=lote_leche, destino=destino,
                                          litros=destino.litros)
            restante -= destino.litros
        else:
            # Se usa una parte: el destino se parte en dos, el total del lote de leche no cambia.
            destino.litros -= restante
            destino.save(update_fields=["litros"])
            parte = DestinoLeche.objects.create(lote=lote_leche, tipo=TipoDestino.ELABORACION_QUESO, litros=restante,
                                                nota=f"Lote de queso {lote_queso.codigo}", creado_por=usuario)
            LoteQuesoLeche.objects.create(lote_queso=lote_queso, lote_leche=lote_leche, destino=parte, litros=restante)
            restante = CERO
    # 2) El resto, del saldo sin destino.
    if restante > 0:
        destino = leche.asignar_destino(usuario, lote_leche, tipo=TipoDestino.ELABORACION_QUESO, litros=restante,
                                        nota=f"Lote de queso {lote_queso.codigo}")
        LoteQuesoLeche.objects.create(lote_queso=lote_queso, lote_leche=lote_leche, destino=destino, litros=restante)

    inventario.registrar(usuario, item=Item.LECHE, tipo=TipoMovimiento.SALIDA, motivo=Motivo.ELABORACION,
                         cantidad=litros, unidad=Unidad.L, lote_leche=lote_leche, lote_queso=lote_queso)
    auditoria.registrar("usar_en_queso", "lotes_leche", lote_leche.pk,
                        cambios={"lote_queso": lote_queso.codigo, "litros": litros})


# --- Iniciar ---------------------------------------------------------------------------------

def _siguiente_numero(fecha) -> int:
    # Bloquea los lotes del día para que dos altas simultáneas no tomen el mismo número.
    list(LoteQueso.objects.select_for_update().filter(fecha=fecha).values_list("pk", flat=True))
    return (LoteQueso.objects.filter(fecha=fecha).aggregate(m=Max("numero"))["m"] or 0) + 1


@transaction.atomic
def iniciar_lote(usuario, *, fecha: datetime.date, origenes: list[dict], insumos: list[dict] | None = None,
                 observaciones: str = "", id=None) -> tuple[LoteQueso, bool]:
    """origenes: [{"lote_leche": LoteLeche | id, "litros": Decimal}]
    insumos:  [{"insumo": Insumo | id, "cantidad": Decimal}]  (se reservan)
    Devuelve (lote, creado). Con un `id` ya existente devuelve el lote sin duplicar."""
    if id is not None:
        existente = LoteQueso.objects.filter(pk=id).first()
        if existente is not None:
            return existente, False
    if fecha > leche.hoy():
        raise ReglaNegocio("No se puede iniciar un lote de queso con fecha futura.")
    if not origenes:
        raise ReglaNegocio("Elegí al menos un lote de leche de origen.")

    ids_leche = [str(getattr(o["lote_leche"], "pk", o["lote_leche"])) for o in origenes]
    if len(set(ids_leche)) != len(ids_leche):
        raise ReglaNegocio("Un lote de leche aparece dos veces.")
    lotes = {str(l.pk): l for l in LoteLeche.objects.filter(pk__in=ids_leche)}
    if len(lotes) != len(ids_leche):
        raise ReglaNegocio("Hay un lote de leche que no existe.")
    litros = [Decimal(o["litros"]) for o in origenes]
    if any(l_ <= 0 for l_ in litros):
        raise ReglaNegocio("Los litros de cada lote de leche tienen que ser mayores a cero.")

    insumos = insumos or []
    ids_insumo = [str(getattr(i["insumo"], "pk", i["insumo"])) for i in insumos]
    if len(set(ids_insumo)) != len(ids_insumo):
        raise ReglaNegocio("Un insumo aparece dos veces.")
    catalogo = {str(i.pk): i for i in Insumo.objects.filter(pk__in=ids_insumo)}
    if len(catalogo) != len(ids_insumo):
        raise ReglaNegocio("Hay un insumo que no existe.")

    lote = LoteQueso(fecha=fecha, numero=_siguiente_numero(fecha), litros_leche=sum(litros, CERO),
                     observaciones=observaciones)
    if id is not None:
        lote.id = id
    lote.save()

    for lote_id, cantidad in zip(ids_leche, litros):
        _tomar_leche(usuario, lote, lotes[lote_id], cantidad)

    for item, insumo_id in zip(insumos, ids_insumo):
        cantidad = Decimal(item["cantidad"])
        if cantidad < 0:
            raise ReglaNegocio("Las cantidades de insumos no pueden ser negativas.")
        insumo = catalogo[insumo_id]
        LoteQuesoInsumo.objects.create(lote_queso=lote, insumo=insumo, cantidad_declarada=cantidad)
        if cantidad > 0:
            inventario.reservar(usuario, insumo, cantidad, lote)

    auditoria.registrar("iniciar_elaboracion", "lotes_queso", lote.pk, cambios={
        "leche": {lotes[i].codigo: c for i, c in zip(ids_leche, litros)},
        "insumos": {catalogo[i].nombre: Decimal(x["cantidad"]) for x, i in zip(insumos, ids_insumo)},
    })
    return lote, True


# --- Cerrar (o corregir después de un rechazo) -----------------------------------------------

def _queso_en_inventario(lote: LoteQueso) -> Decimal:
    movs = MovimientoInventario.objects.filter(item=Item.QUESO, lote_queso=lote)
    e = movs.filter(tipo=TipoMovimiento.ENTRADA).aggregate(t=Sum("cantidad"))["t"] or CERO
    s = movs.filter(tipo=TipoMovimiento.SALIDA).aggregate(t=Sum("cantidad"))["t"] or CERO
    return e - s


def calcular_rendimiento(litros: Decimal, kg: Decimal) -> tuple[Decimal, bool]:
    rendimiento = (Decimal(litros) / Decimal(kg)).quantize(Decimal("0.01"))
    minimo, maximo = rango_rendimiento()
    return rendimiento, not (minimo <= rendimiento <= maximo)


@transaction.atomic
def cerrar_lote(usuario, lote: LoteQueso, *, kg_obtenidos=None, merma_kg=CERO, consumos: list[dict] | None = None,
                observaciones: str | None = None) -> LoteQueso:
    """Registra los kg obtenidos y envía el lote a aprobación.

    consumos: [{"insumo": Insumo | id, "cantidad": Decimal}] con lo usado de verdad. Si no se manda,
    se toma lo declarado al iniciar (o lo ya consumido, si se está corrigiendo un lote rechazado).
    Si se manda, reemplaza todo: un insumo que no figura se toma como no usado."""
    lote = LoteQueso.objects.select_for_update().get(pk=lote.pk)
    if lote.estado not in (EstadoRegistro.BORRADOR, EstadoRegistro.RECHAZADO):
        raise ReglaNegocio(f"El lote está {lote.get_estado_display().lower()}: no se puede cerrar.")
    if kg_obtenidos in (None, ""):
        raise ReglaNegocio("No se puede cerrar el lote sin los kg de queso obtenidos.")
    kg = Decimal(kg_obtenidos)
    merma = Decimal(merma_kg or 0)
    if kg <= 0:
        raise ReglaNegocio("Los kg obtenidos tienen que ser mayores a cero.")
    if merma < 0 or merma >= kg:
        raise ReglaNegocio("La merma tiene que ser menor a los kg obtenidos.")

    corrigiendo = lote.estado == EstadoRegistro.RECHAZADO
    usos = {str(u.insumo_id): u for u in lote.insumos.select_related("insumo")}
    if consumos is None:
        objetivo = {
            k: (u.cantidad_consumida if corrigiendo and u.cantidad_consumida is not None else u.cantidad_declarada)
            for k, u in usos.items()
        }
    else:
        objetivo = {k: CERO for k in usos}
        for c in consumos:
            clave = str(getattr(c["insumo"], "pk", c["insumo"]))
            cantidad = Decimal(c["cantidad"])
            if cantidad < 0:
                raise ReglaNegocio("Las cantidades de insumos no pueden ser negativas.")
            if clave not in usos:
                insumo = Insumo.objects.filter(pk=clave).first()
                if insumo is None:
                    raise ReglaNegocio("Hay un insumo que no existe.")
                usos[clave] = LoteQuesoInsumo.objects.create(lote_queso=lote, insumo=insumo)
            objetivo[clave] = cantidad

    motivo = Motivo.CORRECCION if corrigiendo else Motivo.ELABORACION
    inventario.liberar_reservas(usuario, lote, motivo)
    for clave in sorted(objetivo):
        uso = usos[clave]
        inventario.fijar_consumo(usuario, uso.insumo, objetivo[clave], lote, motivo)
        uso.cantidad_consumida = objetivo[clave]
        uso.save(update_fields=["cantidad_consumida"])

    # Queso terminado al inventario: los kg netos (obtenidos menos merma).
    netos = kg - merma
    diferencia = netos - _queso_en_inventario(lote)
    if diferencia > 0:
        inventario.registrar(usuario, item=Item.QUESO, tipo=TipoMovimiento.ENTRADA,
                             motivo=Motivo.CORRECCION if corrigiendo else Motivo.PRODUCCION,
                             cantidad=diferencia, unidad=Unidad.KG, lote_queso=lote)
    elif diferencia < 0:
        inventario.registrar(usuario, item=Item.QUESO, tipo=TipoMovimiento.SALIDA, motivo=Motivo.CORRECCION,
                             cantidad=-diferencia, unidad=Unidad.KG, lote_queso=lote)

    lote.kg_obtenidos, lote.merma_kg = kg, merma
    lote.rendimiento_l_kg, lote.rendimiento_fuera_de_rango = calcular_rendimiento(lote.litros_leche, kg)
    if observaciones is not None:
        lote.observaciones = observaciones
    lote.cerrado_por = usuario
    lote.fecha_cierre = timezone.now()
    lote.save()
    lote.enviar()
    return lote


# --- Aprobación ------------------------------------------------------------------------------

def _puede_aprobar(usuario, lote: LoteQueso) -> None:
    if not usuario.tiene_permiso(PERMISO_APROBAR):
        raise ReglaNegocio("Solo el Administrador aprueba o rechaza lotes de queso.")
    propio = usuario.pk in (lote.creado_por_id, lote.cerrado_por_id)
    if propio and not usuario.tiene_rol(ADMIN):
        raise ReglaNegocio("No podés aprobar ni rechazar un lote que elaboraste vos.")


@transaction.atomic
def aprobar_lote(usuario, lote: LoteQueso, comentario: str = "") -> LoteQueso:
    lote = LoteQueso.objects.select_for_update().get(pk=lote.pk)
    _puede_aprobar(usuario, lote)
    if lote.estado != EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Solo se aprueba un lote cerrado que está pendiente de aprobación.")
    lote._transicion("aprobar", comentario.strip(), snapshot=True)
    return lote


@transaction.atomic
def rechazar_lote(usuario, lote: LoteQueso, comentario: str) -> LoteQueso:
    lote = LoteQueso.objects.select_for_update().get(pk=lote.pk)
    _puede_aprobar(usuario, lote)
    if lote.estado != EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Solo se rechaza un lote que está pendiente de aprobación.")
    if not (comentario or "").strip():
        raise ReglaNegocio("Para rechazar un lote hace falta un comentario que diga qué corregir.")
    lote.rechazar(comentario)
    return lote


@transaction.atomic
def cancelar_lote(usuario, lote: LoteQueso, motivo: str) -> LoteQueso:
    """Cancela una elaboración que no se cerró: libera los insumos y la leche vuelve a quedar
    destinada a queso, lista para otro lote."""
    lote = LoteQueso.objects.select_for_update().get(pk=lote.pk)
    if lote.estado != EstadoRegistro.BORRADOR:
        raise ReglaNegocio("Solo se cancela un lote que todavía está en elaboración.")
    if lote.creado_por_id != usuario.pk and not usuario.tiene_permiso(PERMISO_APROBAR):
        raise ReglaNegocio("Solo quien inició el lote o el Administrador pueden cancelarlo.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para cancelar hace falta indicar el motivo.")
    inventario.liberar_reservas(usuario, lote, Motivo.CANCELACION)
    for origen in lote.origenes.select_related("lote_leche").filter(destino__isnull=False):
        inventario.registrar(usuario, item=Item.LECHE, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.CANCELACION,
                             cantidad=origen.litros, unidad=Unidad.L, lote_leche=origen.lote_leche, lote_queso=lote)
        origen.destino = None
        origen.save(update_fields=["destino"])
    lote.anular(motivo)
    return lote


# --- Consultas -------------------------------------------------------------------------------

def stock_queso() -> list[dict]:
    """Queso terminado por lote: lo que entró, lo que salió y lo que queda."""
    filas = (MovimientoInventario.objects.filter(item=Item.QUESO)
             .values("lote_queso").annotate(
                 entradas=Sum("cantidad", filter=Q(tipo=TipoMovimiento.ENTRADA)),
                 salidas=Sum("cantidad", filter=Q(tipo=TipoMovimiento.SALIDA))))
    lotes = {l.pk: l for l in LoteQueso.objects.filter(pk__in=[f["lote_queso"] for f in filas])}
    resultado = []
    for f in filas:
        lote = lotes[f["lote_queso"]]
        kg = (f["entradas"] or CERO) - (f["salidas"] or CERO)
        if kg <= 0:
            continue
        resultado.append({"lote_queso": lote.pk, "codigo": lote.codigo, "fecha": lote.fecha, "estado": lote.estado,
                          "kg": kg, "disponible_para_venta": lote.estado == EstadoRegistro.APROBADO})
    resultado.sort(key=lambda r: (r["fecha"], r["codigo"]))
    return resultado


def resumen_inventario_queso() -> dict:
    filas = stock_queso()
    return {
        "lotes": filas,
        "kg_disponibles": sum((f["kg"] for f in filas if f["disponible_para_venta"]), CERO),
        "kg_en_revision": sum((f["kg"] for f in filas if not f["disponible_para_venta"]), CERO),
    }


def inventario_leche(fecha: datetime.date | None = None) -> dict:
    filas = lotes_leche_disponibles(fecha)
    return {
        "dias": DIAS_LECHE_DISPONIBLE,
        "lotes": filas,
        "litros_destinados_a_queso": sum((f["destinado_a_queso"] for f in filas), CERO),
        "litros_sin_destino": sum((f["sin_destino"] for f in filas), CERO),
        "litros_disponibles_para_queso": sum((f["total"] for f in filas), CERO),
    }


def _historial(entidad, entidad_id) -> list[dict]:
    return [{
        "fecha": a.fecha, "accion": a.accion, "usuario": a.usuario.nombre if a.usuario else None,
        "motivo": a.motivo, "cambios": a.cambios,
    } for a in Auditoria.objects.filter(entidad=entidad, entidad_id=str(entidad_id)).select_related("usuario").order_by("id")]


def trazabilidad(lote: LoteQueso) -> dict:
    """Cadena completa de un lote de queso: vacas → lotes de leche → lote de queso → insumos → clientes."""
    from apps.rodeo.models import OrdeneVaca

    origenes = []
    for o in lote.origenes.select_related("lote_leche"):
        ll = o.lote_leche
        vacas = [{"caravana": ov.animal.caravana, "nombre": ov.animal.nombre, "litros": ov.litros}
                 for ov in OrdeneVaca.objects.filter(lote_leche=ll).select_related("animal")]
        origenes.append({
            "lote_leche": ll.pk, "codigo": ll.codigo, "fecha": ll.fecha, "ordene": ll.ordene,
            "litros_usados": o.litros, "litros_del_lote": ll.litros, "vigente": o.destino_id is not None,
            "grasa_pct": ll.grasa_pct, "proteina_pct": ll.proteina_pct, "temperatura_c": ll.temperatura_c,
            "estado": ll.estado, "vacas": vacas,
        })
    insumos = []
    for u in lote.insumos.select_related("insumo"):
        proveedores = sorted(set(
            MovimientoInventario.objects.filter(insumo=u.insumo, tipo=TipoMovimiento.ENTRADA, motivo=Motivo.COMPRA,
                                                fecha__lte=lote.fecha_cierre or lote.fecha_modificacion)
            .exclude(lote_proveedor="").order_by("-fecha").values_list("lote_proveedor", flat=True)[:3]
        ))
        insumos.append({"insumo": u.insumo_id, "nombre": u.insumo.nombre, "unidad": u.insumo.unidad,
                        "declarada": u.cantidad_declarada, "consumida": u.cantidad_consumida,
                        "lotes_proveedor_recientes": proveedores})
    movimientos = [{
        "fecha": m.fecha, "item": m.item, "tipo": m.tipo, "motivo": m.motivo, "cantidad": m.cantidad,
        "unidad": m.unidad, "insumo": m.insumo.nombre if m.insumo else None,
        "lote_leche": m.lote_leche.codigo if m.lote_leche else None,
        "usuario": m.usuario.nombre if m.usuario else None,
    } for m in lote.movimientos_inventario.select_related("insumo", "lote_leche", "usuario").order_by("fecha")]
    return {
        "lote": lote.pk, "codigo": lote.codigo, "estado": lote.estado,
        "origen_leche": origenes,
        "insumos": insumos,
        "movimientos": movimientos,
        "queso_en_stock_kg": _queso_en_inventario(lote),
        # Las ventas (y por lo tanto los clientes) se registran en la Fase 4.
        "clientes": [],
        "historial": _historial("lotes_queso", lote.pk),
    }


def usos_de_lote_leche(lote_leche: LoteLeche) -> list[dict]:
    """El otro sentido de la cadena: en qué lotes de queso terminó un lote de leche."""
    return [{
        "lote_queso": o.lote_queso_id, "codigo": o.lote_queso.codigo, "fecha": o.lote_queso.fecha,
        "estado": o.lote_queso.estado, "litros": o.litros, "vigente": o.destino_id is not None,
    } for o in LoteQuesoLeche.objects.filter(lote_leche=lote_leche).select_related("lote_queso")]
