"""Piezas comunes para las vistas de los módulos."""
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.core.contexto import fijar_usuario
from apps.cuentas.permisos import requiere_permiso


def fecha_param(valor, nombre="fecha"):
    if not valor:
        return None
    fecha = parse_date(valor)
    if fecha is None:
        raise ValidationError({nombre: "Fecha inválida, usá AAAA-MM-DD."})
    return fecha


class PermisosPorAccion:
    """Mixin para ViewSets: PERMISOS = {"accion": "permiso"}; las acciones sin entrada usan PERMISO_POR_DEFECTO."""

    PERMISOS: dict = {}
    PERMISO_POR_DEFECTO = ""

    def get_permissions(self):
        return [requiere_permiso(self.PERMISOS.get(self.action, self.PERMISO_POR_DEFECTO))()]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        fijar_usuario(request.user)


class Paginacion(PageNumberPagination):
    """50 por página; el cliente puede pedir hasta 500 con ?page_size=."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
