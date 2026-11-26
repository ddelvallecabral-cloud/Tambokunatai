"""Gastos operativos y su aprobación.

Un gasto que no supera GASTO_MONTO_APROBACION se aprueba solo. Uno que lo supera queda pendiente
hasta que el Administrador lo apruebe o lo rechace con un comentario. Si lo carga el propio
Administrador, queda aprobado por él.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum

from apps.core.archivos import validar_comprobante
from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.leche import servicios as leche

from .models import Categoria, CentroCosto, Gasto

PERMISO_APROBAR = "gastos.gasto.aprobar"
PERMISO_VER_TODOS = "gastos.ver_todos"
CAMPOS = ("fecha", "categoria", "centro_costo", "monto", "descripcion", "proveedor", "comprobante_numero")


def hoy():
    return leche.hoy()


def umbral() -> int:
    return settings.GASTO_MONTO_APROBACION


def visibles_para(usuario):
    """El Administrador ve todos los gastos; los demás, solo los que cargaron ellos."""
    qs = Gasto.objects.select_related("proveedor", "creado_por", "aprobado_por")
    return qs if usuario.tiene_permiso(PERMISO_VER_TODOS) else qs.filter(creado_por=usuario)


def _validar(datos: dict) -> None:
    if datos.get("fecha") and datos["fecha"] > hoy():
        raise ReglaNegocio("No se puede cargar un gasto con fecha futura.")
    if "monto" in datos and int(datos["monto"]) <= 0:
        raise ReglaNegocio("El monto tiene que ser mayor a cero.")
    if "descripcion" in datos and not (datos["descripcion"] or "").strip():
        raise ReglaNegocio("Contá en pocas palabras en qué se gastó.")
    if datos.get("categoria") and datos["categoria"] not in Categoria.values:
        raise ReglaNegocio("Categoría inválida.")
    if datos.get("centro_costo") and datos["centro_costo"] not in CentroCosto.values:
        raise ReglaNegocio("Centro de costo inválido.")


def _poner_comprobante(gasto: Gasto, archivo) -> None:
    if archivo:
        gasto._tipo_comprobante = validar_comprobante(archivo)
        gasto.comprobante = archivo


def _decidir(usuario, gasto: Gasto) -> Gasto:
    """Envía el gasto y, si corresponde, lo aprueba en el momento."""
    gasto.enviar()
    if gasto.monto <= umbral():
        gasto.aprobacion_automatica = True
        gasto._transicion("aprobar", f"Aprobado automáticamente: no supera Gs. {umbral():,}".replace(",", "."), snapshot=True)
    elif usuario.tiene_permiso(PERMISO_APROBAR):
        gasto.aprobacion_automatica = False
        gasto._transicion("aprobar", "Cargado por el Administrador", snapshot=True)
    return gasto


@transaction.atomic
def registrar_gasto(usuario, *, comprobante=None, id=None, **datos) -> tuple[Gasto, bool]:
    if id is not None and (existente := Gasto.objects.filter(pk=id).first()):
        return existente, False
    datos.setdefault("fecha", hoy())
    _validar(datos)
    gasto = Gasto(**{k: v for k, v in datos.items() if k in CAMPOS})
    if id is not None:
        gasto.id = id
    _poner_comprobante(gasto, comprobante)
    gasto.save()
    return _decidir(usuario, gasto), True


@transaction.atomic
def corregir_gasto(usuario, gasto: Gasto, *, comprobante=None, **datos) -> Gasto:
    """Quien lo cargó corrige un gasto pendiente o rechazado. Un rechazado vuelve a enviarse."""
    gasto = Gasto.objects.select_for_update().get(pk=gasto.pk)
    if gasto.creado_por_id != usuario.pk:
        raise ReglaNegocio("Solo quien cargó el gasto lo puede corregir.")
    if gasto.estado not in (EstadoRegistro.PENDIENTE, EstadoRegistro.RECHAZADO):
        raise ReglaNegocio("Un gasto aprobado o anulado ya no se corrige. Si hay un error, pedile al Administrador que lo anule.")
    _validar(datos)
    for k, v in datos.items():
        if k in CAMPOS:
            setattr(gasto, k, v)
    _poner_comprobante(gasto, comprobante)
    estaba_rechazado = gasto.estado == EstadoRegistro.RECHAZADO
    gasto.save()
    if estaba_rechazado:
        return _decidir(usuario, gasto)
    if gasto.monto <= umbral() or usuario.tiene_permiso(PERMISO_APROBAR):
        # Bajó del umbral al corregirlo: se aprueba ahora.
        gasto.aprobacion_automatica = gasto.monto <= umbral()
        gasto._transicion("aprobar", "Aprobado automáticamente al corregirlo" if gasto.aprobacion_automatica
                          else "Cargado por el Administrador", snapshot=True)
    return gasto


def _solo_admin(usuario, accion: str):
    if not usuario.tiene_permiso(PERMISO_APROBAR):
        raise ReglaNegocio(f"Solo el Administrador puede {accion} gastos.")


@transaction.atomic
def aprobar_gasto(usuario, gasto: Gasto, comentario: str = "") -> Gasto:
    _solo_admin(usuario, "aprobar")
    gasto = Gasto.objects.select_for_update().get(pk=gasto.pk)
    if gasto.estado != EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Solo se aprueba un gasto pendiente.")
    gasto._transicion("aprobar", (comentario or "").strip(), snapshot=True)
    return gasto


@transaction.atomic
def rechazar_gasto(usuario, gasto: Gasto, comentario: str) -> Gasto:
    _solo_admin(usuario, "rechazar")
    gasto = Gasto.objects.select_for_update().get(pk=gasto.pk)
    if gasto.estado != EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Solo se rechaza un gasto pendiente.")
    if not (comentario or "").strip():
        raise ReglaNegocio("Para rechazar un gasto hace falta un comentario que diga qué está mal.")
    gasto.rechazar(comentario)
    return gasto


@transaction.atomic
def anular_gasto(usuario, gasto: Gasto, motivo: str) -> Gasto:
    _solo_admin(usuario, "anular")
    gasto = Gasto.objects.select_for_update().get(pk=gasto.pk)
    if gasto.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El gasto ya está anulado.")
    if not (motivo or "").strip():
        raise ReglaNegocio("Para anular un gasto hace falta el motivo.")
    gasto.anular(motivo)
    return gasto


def resumen(usuario, desde=None, hasta=None) -> dict:
    qs = visibles_para(usuario)
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    aprobados = qs.filter(estado=EstadoRegistro.APROBADO)
    pendientes = qs.filter(estado=EstadoRegistro.PENDIENTE)
    return {
        "umbral_aprobacion": umbral(),
        "total_aprobado": aprobados.aggregate(t=Sum("monto"))["t"] or 0,
        "pendientes": pendientes.count(),
        "total_pendiente": pendientes.aggregate(t=Sum("monto"))["t"] or 0,
        "rechazados": qs.filter(estado=EstadoRegistro.RECHAZADO).count(),
        "por_categoria": [{"categoria": f["categoria"], "total": f["t"], "cantidad": f["n"]}
                          for f in aprobados.values("categoria").annotate(t=Sum("monto"), n=Count("id")).order_by("-t")],
        "por_centro": [{"centro_costo": f["centro_costo"], "total": f["t"]}
                       for f in aprobados.values("centro_costo").annotate(t=Sum("monto")).order_by("-t")],
    }


def pendientes_de_aprobacion() -> dict:
    """Para la bandeja del Administrador: todo lo que espera su decisión."""
    from apps.leche.models import LoteLeche
    from apps.queso.models import LoteQueso

    return {
        "gastos": Gasto.objects.filter(estado=EstadoRegistro.PENDIENTE).count(),
        "lotes_queso": LoteQueso.objects.filter(estado=EstadoRegistro.PENDIENTE).count(),
        "correcciones_leche": LoteLeche.objects.filter(estado=EstadoRegistro.PENDIENTE).count(),
    }
