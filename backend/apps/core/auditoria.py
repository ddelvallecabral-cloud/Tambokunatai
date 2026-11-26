"""Escritura y verificación del registro de auditoría.

Cada fila guarda el hash SHA-256 de su contenido más el hash de la fila anterior.
Si alguien modifica o borra una fila directamente en la base, la cadena se rompe
y `verificar_cadena()` indica dónde.
"""
import datetime
import decimal
import hashlib
import json
import uuid

from django.db import connection, transaction

from .contexto import contexto_actual, usuario_actual

# Número fijo para el candado de PostgreSQL que serializa las escrituras de la cadena.
_CANDADO_AUDITORIA = 7_340_021


def a_json(valor):
    """Convierte valores de modelo a algo que JSON entiende, de forma estable."""
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        return valor.isoformat()
    if isinstance(valor, (decimal.Decimal, uuid.UUID)):
        return str(valor)
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [a_json(v) for v in valor]
    return valor


def _calcular_hash(datos: dict) -> str:
    texto = json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _contenido_hash(fila) -> dict:
    return {
        "anterior": fila.hash_anterior,
        "fecha": fila.fecha.isoformat(),
        "usuario": str(fila.usuario_id) if fila.usuario_id else None,
        "accion": fila.accion,
        "entidad": fila.entidad,
        "entidad_id": fila.entidad_id,
        "cambios": fila.cambios,
        "motivo": fila.motivo,
    }


def _rol_de(usuario) -> str:
    if usuario is None:
        return ""
    roles = getattr(usuario, "roles_codigos", None)
    return ",".join(sorted(roles())) if callable(roles) else ""


def registrar(
    accion: str,
    entidad: str,
    entidad_id="",
    *,
    usuario=None,
    cambios: dict | None = None,
    snapshot: dict | None = None,
    motivo: str = "",
    registrado_offline_en=None,
):
    """Agrega una fila a la auditoría. Toma usuario, IP, dispositivo y request_id del contexto."""
    from django.utils import timezone

    from .models import Auditoria

    ctx = contexto_actual()
    usuario = usuario if usuario is not None else usuario_actual()

    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_CANDADO_AUDITORIA])
        ultima = Auditoria.objects.order_by("-id").only("hash").first()
        fila = Auditoria(
            fecha=timezone.now(),
            usuario=usuario,
            rol_activo=_rol_de(usuario),
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id or ""),
            cambios=a_json(cambios or {}),
            snapshot=a_json(snapshot) if snapshot is not None else None,
            motivo=motivo or "",
            ip=ctx.ip,
            dispositivo=ctx.dispositivo,
            request_id=ctx.request_id,
            registrado_offline_en=registrado_offline_en,
            hash_anterior=ultima.hash if ultima else "",
        )
        fila.hash = _calcular_hash(_contenido_hash(fila))
        fila.save()
    return fila


def verificar_cadena() -> dict:
    """Recorre toda la auditoría en orden y devuelve si la cadena está íntegra."""
    from .models import Auditoria

    anterior = ""
    revisadas = 0
    for fila in Auditoria.objects.order_by("id").iterator(chunk_size=2000):
        revisadas += 1
        if fila.hash_anterior != anterior or fila.hash != _calcular_hash(_contenido_hash(fila)):
            return {"integra": False, "filas_revisadas": revisadas, "primera_fila_alterada": fila.id}
        anterior = fila.hash
    return {"integra": True, "filas_revisadas": revisadas, "primera_fila_alterada": None}
