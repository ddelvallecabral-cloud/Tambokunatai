"""Ordeñe por vaca y por sesión, y la tendencia de producción de cada vaca.

La planilla de una sesión (fecha + mañana/tarde) se guarda completa: lo que se envía reemplaza
lo anterior. La suma de las vacas es el total del lote de leche de esa sesión, así el ordeñe por
vaca y los lotes de la Fase 2 nunca muestran números distintos.
"""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.core import auditoria
from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.leche import servicios as leche
from apps.leche.models import DESTINO_PENDIENTE, LoteLeche

from .models import SITUACIONES_DE_BAJA, Animal, OrdeneVaca, Situacion

CERO = Decimal("0")
# Variación entre la última semana y la anterior a partir de la cual se marca suba o baja.
UMBRAL_TENDENCIA = Decimal("0.05")


def _lote_de_sesion(fecha, ordene):
    return (LoteLeche.objects.select_for_update()
            .filter(fecha=fecha, ordene=ordene).exclude(estado=EstadoRegistro.ANULADO).first())


@transaction.atomic
def registrar_ordene(usuario, *, fecha: datetime.date, ordene: str, items: list[dict],
                     destino: str = DESTINO_PENDIENTE, motivo: str = "") -> dict:
    """Guarda los litros de cada vaca en una sesión y actualiza el lote de leche de esa sesión.

    items: [{"animal": Animal | id, "litros": Decimal, "observaciones": str}], la planilla completa.
    Es idempotente: reenviar la misma planilla (p. ej. desde el celular sin señal) no cambia nada.
    """
    if fecha > leche.hoy():
        raise ReglaNegocio("No se puede cargar ordeñe de una fecha futura.")
    if not items:
        raise ReglaNegocio("Cargá los litros de al menos una vaca.")

    ids = [str(getattr(i["animal"], "pk", i["animal"])) for i in items]
    if len(set(ids)) != len(ids):
        raise ReglaNegocio("Hay una vaca repetida en la planilla.")
    animales = {str(a.pk): a for a in Animal.objects.filter(pk__in=ids)}
    for i in ids:
        animal = animales.get(i)
        if animal is None:
            raise ReglaNegocio("Hay una vaca que no existe en el rodeo.")
        if animal.situacion in SITUACIONES_DE_BAJA or animal.estado == EstadoRegistro.ANULADO:
            raise ReglaNegocio(f"La vaca {animal.caravana} está dada de baja.")

    nuevos = {str(getattr(i["animal"], "pk", i["animal"])): i for i in items}
    total = sum((Decimal(i["litros"]) for i in items), CERO)
    admin = leche.es_administrador(usuario)
    lote = _lote_de_sesion(fecha, ordene)
    creado = lote is None
    total_anterior = None

    if creado:
        if total <= 0:
            raise ReglaNegocio("El total de la sesión tiene que ser mayor a cero.")
        lote, _ = leche.crear_lote(usuario, fecha=fecha, ordene=ordene, litros=total, destino=destino)
    else:
        if lote.estado == EstadoRegistro.PENDIENTE:
            raise ReglaNegocio(f"El lote {lote.codigo} tiene una corrección esperando aprobación.")
        if not admin:
            if lote.esta_bloqueado:
                raise ReglaNegocio(f"El lote {lote.codigo} está cerrado: solo el Administrador puede corregirlo.")
            if lote.fecha < leche.hoy():
                raise ReglaNegocio(
                    "El ordeñe por vaca de días anteriores solo lo corrige el Administrador. "
                    "Pedile la corrección o proponela desde el lote de leche."
                )
        elif lote.esta_bloqueado and not motivo.strip():
            raise ReglaNegocio("El lote está cerrado: para corregirlo hace falta indicar el motivo.")
        total_anterior = lote.litros
        if total <= 0:
            raise ReglaNegocio("El total de la sesión tiene que ser mayor a cero.")
        leche.editar_lote(usuario, lote, {"litros": total}, motivo)

    anteriores = {str(o.animal_id): o for o in OrdeneVaca.objects.filter(lote_leche=lote)}
    cambios = {}
    for animal_id, item in nuevos.items():
        litros = Decimal(item["litros"])
        obs = item.get("observaciones", "") or ""
        previo = anteriores.pop(animal_id, None)
        caravana = animales[animal_id].caravana
        if previo is None:
            OrdeneVaca.objects.create(lote_leche=lote, animal_id=animal_id, litros=litros,
                                      observaciones=obs, creado_por=usuario)
            cambios[caravana] = [None, litros]
        elif previo.litros != litros or previo.observaciones != obs:
            cambios[caravana] = [previo.litros, litros]
            previo.litros, previo.observaciones = litros, obs
            previo.save()
    for previo in anteriores.values():
        cambios[previo.animal.caravana] = [previo.litros, None]
        previo.delete()

    if cambios:
        auditoria.registrar("ordene_por_vaca", "lotes_leche", lote.pk, cambios=cambios, motivo=motivo)
    return {"lote": LoteLeche.objects.get(pk=lote.pk), "creado": creado,
            "total": total, "total_anterior": total_anterior, "vacas_cambiadas": len(cambios)}


def planilla(fecha: datetime.date, ordene: str) -> dict:
    """Vacas para cargar en una sesión: las que están en ordeñe más las que ya tienen litros cargados."""
    lote = LoteLeche.objects.filter(fecha=fecha, ordene=ordene).exclude(estado=EstadoRegistro.ANULADO).first()
    cargados = {}
    if lote is not None:
        cargados = {o.animal_id: o for o in OrdeneVaca.objects.filter(lote_leche=lote)}
    animales = (Animal.objects.exclude(estado=EstadoRegistro.ANULADO)
                .filter(Q(situacion=Situacion.EN_ORDENE) | Q(pk__in=list(cargados)))
                .order_by("caravana"))
    filas = [{
        "animal": a.pk, "caravana": a.caravana, "nombre": a.nombre,
        "litros": cargados[a.pk].litros if a.pk in cargados else None,
        "observaciones": cargados[a.pk].observaciones if a.pk in cargados else "",
    } for a in animales]
    return {
        "fecha": fecha, "ordene": ordene,
        "lote": None if lote is None else {
            "id": lote.pk, "codigo": lote.codigo, "litros": lote.litros, "estado": lote.estado,
            "con_detalle_por_vaca": bool(cargados),
        },
        "vacas": filas,
    }


def _litros_por_animal(desde, hasta, animales=None) -> dict:
    qs = OrdeneVaca.objects.filter(lote_leche__fecha__gte=desde, lote_leche__fecha__lte=hasta).exclude(
        lote_leche__estado=EstadoRegistro.ANULADO)
    if animales is not None:
        qs = qs.filter(animal__in=animales)
    return {
        f["animal"]: (f["litros"], f["dias"])
        for f in qs.values("animal").annotate(litros=Sum("litros"), dias=Count("lote_leche__fecha", distinct=True))
    }


def tendencia(promedio_actual, promedio_anterior) -> str | None:
    if not promedio_actual or not promedio_anterior:
        return None
    variacion = (promedio_actual - promedio_anterior) / promedio_anterior
    if variacion >= UMBRAL_TENDENCIA:
        return "sube"
    if variacion <= -UMBRAL_TENDENCIA:
        return "baja"
    return "estable"


def produccion_por_animal(fecha: datetime.date | None = None, animales=None) -> dict:
    """Promedio diario de cada vaca en los últimos 7 días contra los 7 anteriores."""
    fecha = fecha or leche.hoy()
    semana = _litros_por_animal(fecha - datetime.timedelta(days=6), fecha, animales)
    anterior = _litros_por_animal(fecha - datetime.timedelta(days=13), fecha - datetime.timedelta(days=7), animales)
    resultado = {}
    for animal_id in set(semana) | set(anterior):
        act = semana.get(animal_id)
        ant = anterior.get(animal_id)
        prom_act = (act[0] / act[1]).quantize(Decimal("0.1")) if act else None
        prom_ant = (ant[0] / ant[1]).quantize(Decimal("0.1")) if ant else None
        resultado[animal_id] = {
            "promedio_7d": prom_act, "promedio_7d_anterior": prom_ant, "tendencia": tendencia(prom_act, prom_ant),
        }
    return resultado


def serie_animal(animal: Animal, dias: int = 30, fecha: datetime.date | None = None) -> list[dict]:
    fecha = fecha or leche.hoy()
    desde = fecha - datetime.timedelta(days=dias - 1)
    por_dia = {}
    for o in (OrdeneVaca.objects.filter(animal=animal, lote_leche__fecha__gte=desde, lote_leche__fecha__lte=fecha)
              .exclude(lote_leche__estado=EstadoRegistro.ANULADO).select_related("lote_leche")):
        dia = por_dia.setdefault(o.lote_leche.fecha, {"manana": None, "tarde": None})
        dia[o.lote_leche.ordene] = o.litros
    serie = []
    for i in range(dias):
        d = desde + datetime.timedelta(days=i)
        v = por_dia.get(d, {"manana": None, "tarde": None})
        total = None if v["manana"] is None and v["tarde"] is None else (v["manana"] or CERO) + (v["tarde"] or CERO)
        serie.append({"fecha": d, "manana": v["manana"], "tarde": v["tarde"], "total": total})
    return serie
