from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso
from apps.queso import servicios as queso

from . import servicios
from .models import Insumo, Motivo, MovimientoInventario
from .serializers import EntradaSerializer, InsumoSerializer, MovimientoSerializer, SalidaAjusteSerializer


class InsumoViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Insumos con su stock calculado. Filtros: activo=0|1, bajo_minimo=1."""

    serializer_class = InsumoSerializer
    http_method_names = ["get", "post", "patch"]
    PERMISOS = {"list": "inventario.ver", "retrieve": "inventario.ver",
                "create": "inventario.catalogo.gestionar", "partial_update": "inventario.catalogo.gestionar",
                "entrada": "inventario.entrada.registrar", "salida": "inventario.ajuste.aprobar"}
    PERMISO_POR_DEFECTO = "inventario.catalogo.gestionar"

    def get_queryset(self):
        qs = servicios.con_stock()
        p = self.request.query_params
        if self.action == "list":
            if p.get("activo") in ("0", "1"):
                qs = qs.filter(activo=p["activo"] == "1")
            if p.get("bajo_minimo") == "1":
                qs = qs.filter(bajo_minimo=True)
        return qs.order_by("nombre")

    def _respuesta(self, insumo, codigo=status.HTTP_200_OK):
        return Response(InsumoSerializer(servicios.con_stock().get(pk=insumo.pk)).data, status=codigo)

    def create(self, request, *args, **kwargs):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return self._respuesta(datos.save(), status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        insumo = Insumo.objects.get(pk=kwargs["pk"])
        datos = self.get_serializer(insumo, data=request.data, partial=True)
        datos.is_valid(raise_exception=True)
        return self._respuesta(datos.save())

    @action(detail=True, methods=["post"])
    def entrada(self, request, pk=None):
        insumo = self.get_object()
        datos = EntradaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        if datos.validated_data["motivo"] == Motivo.AJUSTE and not request.user.tiene_permiso("inventario.ajuste.aprobar"):
            return Response({"detail": "Solo el Administrador registra ajustes de inventario."}, status=403)
        servicios.entrada(request.user, insumo, **datos.validated_data)
        return self._respuesta(insumo, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def salida(self, request, pk=None):
        insumo = self.get_object()
        datos = SalidaAjusteSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        servicios.salida_por_ajuste(request.user, insumo, **datos.validated_data)
        return self._respuesta(insumo, status.HTTP_201_CREATED)


class MovimientoViewSet(PermisosPorAccion, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Movimientos (solo lectura). Filtros: item, tipo, insumo, lote_leche, lote_queso, desde, hasta."""

    serializer_class = MovimientoSerializer
    PERMISO_POR_DEFECTO = "inventario.ver"

    def get_queryset(self):
        qs = MovimientoInventario.objects.select_related("insumo", "lote_leche", "lote_queso", "usuario")
        p = self.request.query_params
        for campo in ("item", "tipo", "insumo", "lote_leche", "lote_queso", "motivo"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if desde := fecha_param(p.get("desde"), "desde"):
            qs = qs.filter(fecha__date__gte=desde)
        if hasta := fecha_param(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__date__lte=hasta)
        return qs.order_by("-fecha")


@api_view(["GET"])
@permission_classes([requiere_permiso("inventario.ver")])
def inventario_leche(request):
    return Response(queso.inventario_leche(fecha_param(request.query_params.get("fecha"))))


@api_view(["GET"])
@permission_classes([requiere_permiso("inventario.ver")])
def inventario_queso(request):
    return Response(queso.resumen_inventario_queso())
