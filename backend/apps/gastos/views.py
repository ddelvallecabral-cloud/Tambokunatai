from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core import archivos
from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso

from . import servicios
from .serializers import GastoEntradaSerializer, GastoSerializer


class GastoViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Gastos. El Administrador ve todos; los demás, solo los suyos.
    Filtros: desde, hasta, categoria, centro_costo, estado, proveedor, buscar."""

    serializer_class = GastoSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    PERMISOS = {"list": "gastos.ver", "retrieve": "gastos.ver", "comprobante": "gastos.ver", "resumen": "gastos.ver",
                "create": "gastos.gasto.registrar", "corregir": "gastos.gasto.registrar",
                "aprobar": "gastos.gasto.aprobar", "rechazar": "gastos.gasto.aprobar", "anular": "gastos.gasto.aprobar"}
    PERMISO_POR_DEFECTO = "gastos.gasto.aprobar"

    def get_queryset(self):
        qs = servicios.visibles_para(self.request.user)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if desde := fecha_param(p.get("desde"), "desde"):
            qs = qs.filter(fecha__gte=desde)
        if hasta := fecha_param(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__lte=hasta)
        for campo in ("categoria", "centro_costo", "estado", "proveedor"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("buscar"):
            qs = qs.filter(descripcion__icontains=p["buscar"].strip())
        return qs.order_by("-fecha", "-fecha_creacion")

    def _respuesta(self, gasto, codigo=status.HTTP_200_OK):
        return Response(GastoSerializer(servicios.visibles_para(self.request.user).get(pk=gasto.pk)).data, status=codigo)

    def _datos(self, request):
        datos = GastoEntradaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return dict(datos.validated_data)

    def create(self, request):
        datos = self._datos(request)
        gasto, creado = servicios.registrar_gasto(request.user, **datos)
        return self._respuesta(gasto, status.HTTP_201_CREATED if creado else status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def corregir(self, request, pk=None):
        datos = self._datos(request)
        datos.pop("id", None)
        return self._respuesta(servicios.corregir_gasto(request.user, self.get_object(), **datos))

    @action(detail=True, methods=["get"])
    def comprobante(self, request, pk=None):
        gasto = self.get_object()
        if not gasto.comprobante:
            raise Http404
        return archivos.entregar(gasto.comprobante, f"comprobante-gasto-{gasto.fecha:%Y%m%d}")

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        return self._respuesta(servicios.aprobar_gasto(request.user, self.get_object(), str(request.data.get("comentario", ""))))

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        return self._respuesta(servicios.rechazar_gasto(request.user, self.get_object(), str(request.data.get("comentario", ""))))

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        return self._respuesta(servicios.anular_gasto(request.user, self.get_object(), str(request.data.get("motivo", ""))))

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        p = request.query_params
        return Response(servicios.resumen(request.user, fecha_param(p.get("desde"), "desde"), fecha_param(p.get("hasta"), "hasta")))


@api_view(["GET"])
@permission_classes([requiere_permiso("gastos.gasto.aprobar")])
def bandeja(request):
    """Cuántas cosas esperan la decisión del Administrador."""
    return Response(servicios.pendientes_de_aprobacion())


