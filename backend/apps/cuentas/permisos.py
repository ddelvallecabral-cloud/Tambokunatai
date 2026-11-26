"""Restricción de endpoints por permiso o por rol.

Por permiso (recomendado, es granular):

    class LoteQuesoViewSet(viewsets.ModelViewSet):
        permission_classes = [requiere_permiso("queso.ver")]

    @action(detail=True, methods=["post"], permission_classes=[requiere_permiso("queso.lote.aprobar")])
    def aprobar(self, request, pk=None): ...

Por rol (para casos simples):

    permission_classes = [requiere_rol(ADMIN)]

También como decorador de una vista basada en función:

    @api_view(["GET"])
    @permiso_requerido("reportes.financieros")
    def estado_resultados(request): ...
"""
from functools import wraps

from rest_framework.permissions import BasePermission
from rest_framework.response import Response


def requiere_permiso(*codigos: str) -> type[BasePermission]:
    class TienePermiso(BasePermission):
        message = "No tenés permiso para esta acción."

        def has_permission(self, request, view):
            usuario = request.user
            return bool(usuario and usuario.is_authenticated and usuario.tiene_permiso(*codigos))

    TienePermiso.__name__ = f"TienePermiso[{','.join(codigos)}]"
    return TienePermiso


def requiere_rol(*roles: str) -> type[BasePermission]:
    class TieneRol(BasePermission):
        message = "Tu rol no tiene acceso a esta sección."

        def has_permission(self, request, view):
            usuario = request.user
            return bool(usuario and usuario.is_authenticated and usuario.is_active and usuario.tiene_rol(*roles))

    TieneRol.__name__ = f"TieneRol[{','.join(roles)}]"
    return TieneRol


def permiso_requerido(*codigos: str):
    """Decorador para vistas de función (debajo de @api_view)."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.tiene_permiso(*codigos):
                return Response({"detail": "No tenés permiso para esta acción."}, status=403)
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
