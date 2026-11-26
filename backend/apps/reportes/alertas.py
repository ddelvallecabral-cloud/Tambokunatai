"""Configuración de alertas del Administrador. Se guarda en la tabla `configuracion` (clave "alertas").
Los valores por defecto salen del .env, así que sin tocar nada se comporta como antes."""

import copy
from decimal import Decimal

from django.conf import settings

CLAVE = "alertas"


def por_defecto() -> dict:
    return {
        "produccion_baja": {"activa": bool(getattr(settings, "LECHE_UMBRAL_LITROS_DIARIOS", None)),
                            "litros_minimos": float(getattr(settings, "LECHE_UMBRAL_LITROS_DIARIOS", None) or 0)},
        "rendimiento": {"activa": True, "minimo": float(settings.QUESO_RENDIMIENTO_MIN_L_KG),
                        "maximo": float(settings.QUESO_RENDIMIENTO_MAX_L_KG)},
        "stock_bajo": {"activa": True},
        "cuentas_vencidas": {"activa": True, "dias_gracia": 0},
    }


def _fila():
    from apps.core.models import Configuracion, Establecimiento

    est = Establecimiento.objects.order_by("nombre").first()
    if est is None:
        return None, None
    return est, Configuracion.objects.filter(establecimiento=est, clave=CLAVE).first()


def leer() -> dict:
    datos = por_defecto()
    _, fila = _fila()
    if fila and isinstance(fila.valor, dict):
        for k, v in fila.valor.items():
            if k in datos and isinstance(v, dict):
                datos[k].update({c: v[c] for c in v if c in datos[k]})
    return datos


def validar(nuevo: dict) -> dict:
    """Mezcla lo recibido con lo actual y valida. Devuelve la configuración completa."""
    from apps.core.mixins import ReglaNegocio

    datos = copy.deepcopy(leer())
    for k, v in (nuevo or {}).items():
        if k not in datos or not isinstance(v, dict):
            raise ReglaNegocio(f"Alerta desconocida: {k}.")
        for campo, valor in v.items():
            if campo not in datos[k]:
                raise ReglaNegocio(f"Campo desconocido en {k}: {campo}.")
            if campo == "activa":
                datos[k][campo] = bool(valor)
            else:
                try:
                    numero = float(valor)
                except (TypeError, ValueError):
                    raise ReglaNegocio("Los umbrales tienen que ser números.") from None
                if numero < 0:
                    raise ReglaNegocio("Los umbrales no pueden ser negativos.")
                datos[k][campo] = int(numero) if campo == "dias_gracia" else numero
    r = datos["rendimiento"]
    if r["minimo"] <= 0 or r["maximo"] <= r["minimo"]:
        raise ReglaNegocio("El rendimiento mínimo tiene que ser mayor a cero y menor que el máximo.")
    if datos["produccion_baja"]["activa"] and datos["produccion_baja"]["litros_minimos"] <= 0:
        raise ReglaNegocio("Indicá cuántos litros por día como mínimo esperás.")
    return datos


def guardar(usuario, nuevo: dict) -> dict:
    from apps.core import auditoria
    from apps.core.models import Configuracion, Establecimiento

    datos = validar(nuevo)
    antes = leer()
    est, fila = _fila()
    if est is None:
        est = Establecimiento.objects.create(nombre="Tambo")
    if fila is None:
        Configuracion.objects.create(establecimiento=est, clave=CLAVE, valor=datos, descripcion="Alertas del tablero")
    else:
        fila.valor = datos
        fila.save(update_fields=["valor"])
    auditoria.registrar("configurar_alertas", "configuracion", CLAVE, usuario=usuario, cambios={"antes": antes, "despues": datos})
    return datos


def rango_rendimiento() -> tuple[Decimal, Decimal]:
    r = leer()["rendimiento"]
    return Decimal(str(r["minimo"])), Decimal(str(r["maximo"]))


def litros_minimos() -> Decimal | None:
    p = leer()["produccion_baja"]
    return Decimal(str(p["litros_minimos"])) if p["activa"] and p["litros_minimos"] > 0 else None
