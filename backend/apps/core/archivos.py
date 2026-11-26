"""Comprobantes (fotos o PDF) subidos desde el celular.

Se guardan fuera de la carpeta pública y se entregan solo por la API, a quien puede ver el registro.
"""
import mimetypes
import uuid

from django.conf import settings
from django.http import FileResponse

from .mixins import ReglaNegocio

TIPOS_PERMITIDOS = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic", "image/heif": ".heif",
    "application/pdf": ".pdf",
}
_FIRMAS = (b"\xff\xd8\xff", b"\x89PNG", b"RIFF", b"%PDF", b"\x00\x00\x00")


def _ruta(carpeta: str, instancia, nombre: str) -> str:
    """Nombre al azar (no se puede adivinar) dentro de comprobantes/<carpeta>/<año>/<mes>/."""
    ext = TIPOS_PERMITIDOS.get(getattr(instancia, "_tipo_comprobante", ""), "") or (
        "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "")
    fecha = getattr(instancia, "fecha", None)
    sub = f"{fecha:%Y/%m}" if fecha else "sin-fecha"
    return f"comprobantes/{carpeta}/{sub}/{uuid.uuid4().hex}{ext}"


def ruta_comprobante_gasto(instancia, nombre):
    return _ruta("gastos", instancia, nombre)


def ruta_comprobante_compra(instancia, nombre):
    return _ruta("compras", instancia, nombre)


def validar_comprobante(archivo) -> str:
    """Devuelve el tipo de contenido si el archivo es una foto o un PDF de tamaño razonable."""
    maximo = settings.COMPROBANTE_MAX_MB * 1024 * 1024
    if archivo.size > maximo:
        raise ReglaNegocio(f"El comprobante pesa más de {settings.COMPROBANTE_MAX_MB} MB. Sacá la foto con menos resolución.")
    tipo = (getattr(archivo, "content_type", "") or mimetypes.guess_type(archivo.name)[0] or "").lower()
    if tipo not in TIPOS_PERMITIDOS:
        raise ReglaNegocio("El comprobante tiene que ser una foto (JPG, PNG, WEBP, HEIC) o un PDF.")
    inicio = archivo.read(12)
    archivo.seek(0)
    if not inicio.startswith(_FIRMAS) and b"ftyp" not in inicio:
        raise ReglaNegocio("El archivo no parece una foto ni un PDF.")
    return tipo


def entregar(campo_archivo, nombre_descarga: str) -> FileResponse:
    tipo = mimetypes.guess_type(campo_archivo.name)[0] or "application/octet-stream"
    respuesta = FileResponse(campo_archivo.open("rb"), content_type=tipo)
    ext = "." + campo_archivo.name.rsplit(".", 1)[-1] if "." in campo_archivo.name else ""
    respuesta["Content-Disposition"] = f'inline; filename="{nombre_descarga}{ext}"'
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta
