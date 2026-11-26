from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .mixins import RegistroBloqueado, TransicionInvalida


def manejador_excepciones(exc, context):
    if isinstance(exc, RegistroBloqueado):
        return Response({"detail": str(exc), "codigo": "registro_bloqueado"}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, TransicionInvalida):
        return Response({"detail": str(exc), "codigo": "transicion_invalida"}, status=status.HTTP_409_CONFLICT)
    return exception_handler(exc, context)
