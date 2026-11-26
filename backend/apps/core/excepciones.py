import logging

from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

from .mixins import RegistroBloqueado, ReglaNegocio, TransicionInvalida

log = logging.getLogger("tambo")

ERROR_INTERNO = ("El sistema tuvo un problema al guardar o leer los datos. Probá de nuevo en un rato; "
                 "si sigue pasando, avisale al administrador con la hora en que ocurrió.")


def _conflicto(mensaje: str, codigo: str) -> Response:
    set_rollback()
    return Response({"detail": mensaje, "codigo": codigo}, status=status.HTTP_409_CONFLICT)


def manejador_excepciones(exc, context):
    """Toda respuesta de error de la API es JSON con un `detail` que el usuario final entiende."""
    if isinstance(exc, RegistroBloqueado):
        return _conflicto(str(exc), "registro_bloqueado")
    if isinstance(exc, TransicionInvalida):
        return _conflicto(str(exc), "transicion_invalida")
    if isinstance(exc, ReglaNegocio):
        return _conflicto(str(exc), "regla_de_negocio")
    if isinstance(exc, ProtectedError):
        return _conflicto("No se puede borrar porque otros registros dependen de este. Desactivalo o anulalo.",
                          "protegido")
    if isinstance(exc, IntegrityError):
        log.warning("IntegrityError en %s: %s", context.get("view"), exc)
        return _conflicto("Los datos chocan con un registro que ya existe o no cumplen una regla del sistema. "
                          "Revisalos y probá de nuevo.", "integridad")
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        # Error no previsto: queda en el log con todo el detalle y el usuario recibe un mensaje claro.
        log.exception("Error no previsto en %s", context.get("view"), exc_info=exc)
        set_rollback()
        return Response({"detail": ERROR_INTERNO, "codigo": "error_interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return respuesta
