"""Reglas de negocio de la producción de leche.

Las vistas solo traducen HTTP; todo lo que decide qué se puede hacer vive acá,
para poder probarlo sin pasar por la API.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core import auditoria
from apps.core.mixins import EstadoRegistro, ReglaNegocio  # noqa: F401  (ReglaNegocio se reexporta)

from .models import CERO, DESTINO_PENDIENTE, DestinoLeche, LoteLeche, Ordene, TipoDestino

PERMISO_APROBAR = "leche.lote.aprobar"


def hoy() -> datetime.date:
    return timezone.localdate()


def es_administrador(usuario) -> bool:
    return usuario.tiene_permiso(PERMISO_APROBAR)


# --- Alta -------------------------------------------------------------------------------------

@transaction.atomic
def crear_lote(usuario, *, destino: str = DESTINO_PENDIENTE, **datos) -> tuple[LoteLeche, bool]:
    """Crea el lote de una sesión de ordeñe. Devuelve (lote, creado).

    Si llega un `id` que ya existe (reenvío desde el celular sin señal), devuelve el existente
    sin duplicar. Si `destino` no es "pendiente", asigna todos los litros a ese destino.
    """
    if datos.get("id"):
        existente = LoteLeche.objects.filter(pk=datos["id"]).first()
        if existente is not None:
            return existente, False

    if datos["fecha"] > hoy():
        raise ReglaNegocio("No se puede cargar leche de una fecha futura.")
    duplicado = (
        LoteLeche.objects.filter(fecha=datos["fecha"], ordene=datos["ordene"])
        .exclude(estado=EstadoRegistro.ANULADO)
        .first()
    )
    if duplicado is not None:
        raise ReglaNegocio(
            f"Ya existe el lote {duplicado.codigo} para ese ordeñe. Corregilo en lugar de cargar otro."
        )

    lote = LoteLeche.objects.create(**datos)
    if destino != DESTINO_PENDIENTE:
        asignar_destino(usuario, lote, tipo=destino, litros=lote.litros)
    return lote, True


# --- Destinos ---------------------------------------------------------------------------------

ESTADOS_CON_DESTINOS = {EstadoRegistro.BORRADOR, EstadoRegistro.APROBADO, EstadoRegistro.RECHAZADO}


@transaction.atomic
def asignar_destino(usuario, lote: LoteLeche, *, tipo: str, litros: Decimal, nota: str = "") -> DestinoLeche:
    """Asigna litros del lote a un destino. Nunca se puede asignar más que el saldo disponible."""
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if tipo not in TipoDestino.values:
        raise ReglaNegocio("Destino inválido.")
    if lote.estado not in ESTADOS_CON_DESTINOS:
        raise ReglaNegocio(f"El lote está {lote.get_estado_display().lower()}: no se le pueden asignar destinos.")
    litros = Decimal(litros)
    if litros <= 0:
        raise ReglaNegocio("Los litros tienen que ser mayores a cero.")
    saldo = lote.saldo_disponible
    if litros > saldo:
        raise ReglaNegocio(f"Solo quedan {saldo} L disponibles en {lote.codigo}.")

    destino = DestinoLeche.objects.create(lote=lote, tipo=tipo, litros=litros, nota=nota, creado_por=usuario)
    auditoria.registrar(
        "asignar_destino", "lotes_leche", lote.pk,
        cambios={"destino": tipo, "litros": litros, "saldo": [saldo, saldo - litros]},
    )
    return destino


@transaction.atomic
def quitar_destino(usuario, destino: DestinoLeche, motivo: str = "") -> None:
    """Deshace una asignación. El Operador solo puede en lotes del día; el Administrador siempre."""
    lote = LoteLeche.objects.select_for_update().get(pk=destino.lote_id)
    admin = es_administrador(usuario)
    if lote.estado not in ESTADOS_CON_DESTINOS and not admin:
        raise ReglaNegocio("El lote está cerrado o en revisión: solo el Administrador puede cambiar sus destinos.")
    if lote.fecha < hoy() and not admin:
        raise ReglaNegocio("Solo el Administrador puede quitar destinos de días anteriores.")
    venta = getattr(destino, "uso_venta", None)
    if venta is not None:
        raise ReglaNegocio(
            f"Estos litros ya se vendieron en la venta {venta.venta.codigo}. Para liberarlos hay que anular la venta."
        )
    uso = getattr(destino, "uso_queso", None)
    if uso is not None:
        raise ReglaNegocio(
            f"Estos litros ya se usaron en el lote de queso {uso.lote_queso.codigo}. "
            "Para liberarlos hay que cancelar ese lote de queso."
        )
    auditoria.registrar(
        "quitar_destino", "lotes_leche", lote.pk,
        cambios={"destino": destino.tipo, "litros": destino.litros}, motivo=motivo,
    )
    destino.delete()


# --- Edición ----------------------------------------------------------------------------------

def _normalizar(campo, valor):
    if valor is None:
        return None
    if campo in ("litros", "grasa_pct", "proteina_pct", "temperatura_c"):
        return Decimal(str(valor))
    if campo == "fecha" and isinstance(valor, str):
        return datetime.date.fromisoformat(valor)
    return valor


def _diferencias(lote: LoteLeche, cambios: dict) -> dict:
    return {
        campo: _normalizar(campo, valor)
        for campo, valor in cambios.items()
        if campo in LoteLeche.CAMPOS_EDITABLES and _normalizar(campo, getattr(lote, campo)) != _normalizar(campo, valor)
    }


def _validar_cambios(lote: LoteLeche, cambios: dict) -> None:
    if "litros" in cambios and cambios["litros"] < lote.litros_asignados:
        raise ReglaNegocio(
            f"No se pueden dejar {cambios['litros']} L: ya hay {lote.litros_asignados} L asignados a destinos. "
            "Quitá primero algún destino."
        )
    fecha = cambios.get("fecha", lote.fecha)
    ordene = cambios.get("ordene", lote.ordene)
    if fecha > hoy():
        raise ReglaNegocio("No se puede mover un lote a una fecha futura.")
    if ("fecha" in cambios or "ordene" in cambios) and (
        LoteLeche.objects.filter(fecha=fecha, ordene=ordene).exclude(pk=lote.pk)
        .exclude(estado=EstadoRegistro.ANULADO).exists()
    ):
        raise ReglaNegocio("Ya existe otro lote para esa fecha y ordeñe.")


def _aplicar(lote: LoteLeche, cambios: dict) -> None:
    for campo, valor in cambios.items():
        setattr(lote, campo, valor)


@transaction.atomic
def editar_lote(usuario, lote: LoteLeche, cambios: dict, motivo: str = "") -> str:
    """Edita un lote según quién edita y de qué fecha es. Devuelve qué pasó:

    - "aplicado": el cambio quedó guardado.
    - "pendiente": el cambio quedó propuesto y espera la aprobación del Administrador
      (Operador corrigiendo un lote de un día anterior). El lote no cambia hasta que se apruebe.
    - "sin_cambios": no había nada distinto.
    """
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    cambios = _diferencias(lote, cambios)
    if not cambios:
        return "sin_cambios"
    _validar_cambios(lote, cambios)
    admin = es_administrador(usuario)

    if lote.estado == EstadoRegistro.ANULADO:
        raise ReglaNegocio("El lote está anulado.")

    if admin:
        _aplicar(lote, cambios)
        if lote.esta_bloqueado:
            if not motivo.strip():
                raise ReglaNegocio("Para editar un lote cerrado o aprobado hace falta indicar el motivo.")
            lote.guardar_edicion_autorizada("editar_bloqueado", motivo)
        else:
            lote.save()
        return "aplicado"

    # Operador
    if lote.esta_bloqueado:
        raise ReglaNegocio("El lote está cerrado: solo el Administrador puede editarlo.")
    if lote.estado == EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Este lote ya tiene una corrección esperando aprobación.")

    if lote.fecha < hoy():
        lote.cambios_propuestos = {**auditoria.a_json(cambios), "_motivo": motivo}
        lote.propuesto_por = usuario
        lote._transicion("enviar", motivo)
        auditoria.registrar(
            "proponer_correccion", "lotes_leche", lote.pk,
            cambios={c: [getattr(lote, c), v] for c, v in cambios.items()}, motivo=motivo,
        )
        return "pendiente"

    _aplicar(lote, cambios)
    lote.save()
    return "aplicado"


@transaction.atomic
def aprobar_correccion(usuario, lote: LoteLeche) -> LoteLeche:
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if lote.estado != EstadoRegistro.PENDIENTE or not lote.cambios_propuestos:
        raise ReglaNegocio("Este lote no tiene una corrección pendiente.")
    propuestos = {k: v for k, v in lote.cambios_propuestos.items() if not k.startswith("_")}
    cambios = {c: _normalizar(c, v) for c, v in propuestos.items()}
    _validar_cambios(lote, cambios)
    _aplicar(lote, cambios)
    lote.guardar_edicion_autorizada("aplicar_correccion", lote.cambios_propuestos.get("_motivo", ""))
    lote.cambios_propuestos = None
    lote.aprobar()
    return lote


@transaction.atomic
def rechazar_correccion(usuario, lote: LoteLeche, motivo: str) -> LoteLeche:
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if lote.estado != EstadoRegistro.PENDIENTE:
        raise ReglaNegocio("Este lote no tiene una corrección pendiente.")
    lote.cambios_propuestos = None
    lote.rechazar(motivo)
    return lote


@transaction.atomic
def anular_lote(usuario, lote: LoteLeche, motivo: str) -> LoteLeche:
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if lote.usos_queso.filter(destino__isnull=False).exists():
        raise ReglaNegocio("Este lote de leche ya se usó para elaborar queso: no se puede anular.")
    if lote.ventas.filter(destino__isnull=False).exists():
        raise ReglaNegocio("Este lote de leche ya se vendió: anulá primero la venta.")
    lote.anular(motivo)
    return lote


@transaction.atomic
def cerrar_lote(usuario, lote: LoteLeche) -> LoteLeche:
    lote = LoteLeche.objects.select_for_update().get(pk=lote.pk)
    if lote.saldo_disponible > 0:
        raise ReglaNegocio(f"Quedan {lote.saldo_disponible} L sin destino. Asignalos antes de cerrar el lote.")
    if lote.estado == EstadoRegistro.RECHAZADO:
        lote.estado = EstadoRegistro.BORRADOR
    lote.cerrar()
    return lote


# --- Consultas --------------------------------------------------------------------------------

def con_totales(qs):
    """Agrega litros_asignados a cada lote en una sola consulta."""
    return qs.annotate(
        _asignados=Coalesce(Sum("destinos__litros"), Value(CERO), output_field=DecimalField(max_digits=9, decimal_places=1))
    )


def lotes_validos():
    return LoteLeche.objects.exclude(estado=EstadoRegistro.ANULADO)


def resumen_dia(fecha: datetime.date) -> dict:
    """Litros del día por ordeñe y por destino. "pendiente" = litros todavía sin destino."""
    lotes = lotes_validos().filter(fecha=fecha)
    por_ordene = {o: CERO for o in Ordene.values}
    for fila in lotes.values("ordene").annotate(t=Sum("litros")):
        por_ordene[fila["ordene"]] = fila["t"]
    total = sum(por_ordene.values(), CERO)

    por_destino = {t: CERO for t in TipoDestino.values}
    for fila in DestinoLeche.objects.filter(lote__in=lotes).values("tipo").annotate(t=Sum("litros")):
        por_destino[fila["tipo"]] = fila["t"]
    asignado = sum(por_destino.values(), CERO)
    por_destino[DESTINO_PENDIENTE] = total - asignado

    return {
        "fecha": fecha,
        "total_litros": total,
        "por_ordene": por_ordene,
        "por_destino": por_destino,
        "saldo_disponible": total - asignado,
        "ordenes_cargados": sorted(set(lotes.values_list("ordene", flat=True))),
        "ordenes_faltantes": [o for o in Ordene.values if not lotes.filter(ordene=o).exists()],
        "lotes": lotes.count(),
    }


def formato_litros(valor: Decimal) -> str:
    """1234.5 -> "1.234,5 L" (formato paraguayo)."""
    texto = f"{Decimal(valor):,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{texto.removesuffix(',0')} L"


def umbral_litros_diarios() -> Decimal | None:
    valor = getattr(settings, "LECHE_UMBRAL_LITROS_DIARIOS", None)
    return Decimal(str(valor)) if valor else None


def tablero(fecha: datetime.date | None = None) -> dict:
    """Datos del panel de leche: hoy, mes, últimos 14 días, alertas y correcciones pendientes."""
    fecha = fecha or hoy()
    inicio_mes = fecha.replace(day=1)
    validos = lotes_validos()

    hoy_resumen = resumen_dia(fecha)
    mes = validos.filter(fecha__gte=inicio_mes, fecha__lte=fecha).aggregate(
        litros=Coalesce(Sum("litros"), Value(CERO), output_field=DecimalField(max_digits=12, decimal_places=1)),
        dias=Count("fecha", distinct=True),
    )
    promedio = (mes["litros"] / mes["dias"]).quantize(Decimal("0.1")) if mes["dias"] else CERO

    desde = fecha - datetime.timedelta(days=13)
    por_dia = {
        f["fecha"]: f["t"]
        for f in validos.filter(fecha__gte=desde, fecha__lte=fecha).values("fecha").annotate(t=Sum("litros"))
    }
    serie = [
        {"fecha": desde + datetime.timedelta(days=i), "litros": por_dia.get(desde + datetime.timedelta(days=i), CERO)}
        for i in range(14)
    ]

    alertas = []
    umbral = umbral_litros_diarios()
    if umbral:
        ayer = fecha - datetime.timedelta(days=1)
        litros_ayer = por_dia.get(ayer, CERO)
        if not hoy_resumen["ordenes_faltantes"] and hoy_resumen["total_litros"] < umbral:
            alertas.append({
                "nivel": "advertencia", "fecha": fecha,
                "mensaje": f"Hoy se ordeñaron {formato_litros(hoy_resumen['total_litros'])}, "
                           f"por debajo del mínimo de {formato_litros(umbral)}.",
            })
        if litros_ayer < umbral:
            alertas.append({
                "nivel": "advertencia", "fecha": ayer,
                "mensaje": f"Ayer se ordeñaron {formato_litros(litros_ayer)}, "
                           f"por debajo del mínimo de {formato_litros(umbral)}.",
            })

    return {
        "fecha": fecha,
        "hoy": hoy_resumen,
        "mes": {"desde": inicio_mes, "litros": mes["litros"], "dias_con_carga": mes["dias"], "promedio_diario": promedio},
        "ultimos_14_dias": serie,
        "umbral_litros_diarios": umbral,
        "alertas": alertas,
        "correcciones_pendientes": LoteLeche.objects.filter(estado=EstadoRegistro.PENDIENTE).count(),
        "lotes_con_saldo": con_totales(validos.filter(fecha__gte=fecha - datetime.timedelta(days=3)))
        .filter(_asignados__lt=F("litros"))
        .exclude(estado=EstadoRegistro.CERRADO)
        .count(),
    }
