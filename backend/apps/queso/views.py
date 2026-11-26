from decimal import Decimal

from django.db.models import Avg, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.core.mixins import EstadoRegistro
from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso
from apps.leche import servicios as leche
from apps.leche.models import LoteLeche

from . import servicios
from .models import LoteQueso
from .serializers import CerrarLoteSerializer, ComentarioSerializer, IniciarLoteSerializer, LoteQuesoSerializer


class LoteQuesoViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Lotes de queso. Filtros: estado, desde, hasta, fuera_de_rango=1."""

    serializer_class = LoteQuesoSerializer
    PERMISOS = {"list": "queso.ver", "retrieve": "queso.ver", "trazabilidad": "queso.ver",
                "create": "queso.lote.gestionar", "cancelar": "queso.lote.gestionar",
                "cerrar": "queso.lote.enviar",
                "aprobar": "queso.lote.aprobar", "rechazar": "queso.lote.aprobar"}
    PERMISO_POR_DEFECTO = "queso.lote.aprobar"

    def get_queryset(self):
        qs = LoteQueso.objects.select_related("creado_por", "cerrado_por", "aprobado_por").prefetch_related(
            "origenes__lote_leche", "insumos__insumo")
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("estado"):
            qs = qs.filter(estado=p["estado"])
        else:
            qs = qs.exclude(estado=EstadoRegistro.ANULADO)
        if desde := fecha_param(p.get("desde"), "desde"):
            qs = qs.filter(fecha__gte=desde)
        if hasta := fecha_param(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__lte=hasta)
        if p.get("fuera_de_rango") == "1":
            qs = qs.filter(rendimiento_fuera_de_rango=True)
        return qs.order_by("-fecha", "-numero")

    def _respuesta(self, lote, codigo=status.HTTP_200_OK):
        return Response(LoteQuesoSerializer(self.get_queryset().get(pk=lote.pk)).data, status=codigo)

    def create(self, request):
        datos = IniciarLoteSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        lote, creado = servicios.iniciar_lote(request.user, **datos.validated_data)
        return self._respuesta(lote, status.HTTP_201_CREATED if creado else status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        datos = CerrarLoteSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        lote = servicios.cerrar_lote(request.user, self.get_object(), **datos.validated_data)
        return self._respuesta(lote)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        datos = ComentarioSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return self._respuesta(servicios.aprobar_lote(request.user, self.get_object(), datos.validated_data["comentario"]))

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        datos = ComentarioSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return self._respuesta(servicios.rechazar_lote(request.user, self.get_object(), datos.validated_data["comentario"]))

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        motivo = str(request.data.get("motivo", ""))
        return self._respuesta(servicios.cancelar_lote(request.user, self.get_object(), motivo))

    @action(detail=True, methods=["get"])
    def trazabilidad(self, request, pk=None):
        return Response(servicios.trazabilidad(self.get_object()))


@api_view(["GET"])
@permission_classes([requiere_permiso("queso.ver")])
def leche_disponible(request):
    return Response(servicios.lotes_leche_disponibles(fecha_param(request.query_params.get("fecha"))))


@api_view(["GET"])
@permission_classes([requiere_permiso("queso.ver")])
def resumen(request):
    hoy = leche.hoy()
    mes = LoteQueso.objects.filter(fecha__gte=hoy.replace(day=1), fecha__lte=hoy,
                                   estado__in=[EstadoRegistro.PENDIENTE, EstadoRegistro.APROBADO])
    totales = mes.aggregate(kg=Sum("kg_obtenidos"), litros=Sum("litros_leche"), rendimiento=Avg("rendimiento_l_kg"))
    minimo, maximo = servicios.rango_rendimiento()
    rendimiento_mes = None
    if totales["kg"]:
        rendimiento_mes = (totales["litros"] / totales["kg"]).quantize(Decimal("0.01"))
    return Response({
        "rango_rendimiento": {"min": minimo, "max": maximo},
        "en_elaboracion": LoteQueso.objects.filter(estado=EstadoRegistro.BORRADOR).count(),
        "pendientes_aprobacion": LoteQueso.objects.filter(estado=EstadoRegistro.PENDIENTE).count(),
        "rechazados": LoteQueso.objects.filter(estado=EstadoRegistro.RECHAZADO).count(),
        "mes": {"lotes": mes.count(), "kg_obtenidos": totales["kg"] or 0, "litros_leche": totales["litros"] or 0,
                "rendimiento_l_kg": rendimiento_mes,
                "fuera_de_rango": mes.filter(rendimiento_fuera_de_rango=True).count()},
        "leche_disponible_litros": servicios.inventario_leche(hoy)["litros_disponibles_para_queso"],
        "queso": servicios.resumen_inventario_queso(),
    })


@api_view(["GET"])
@permission_classes([requiere_permiso("leche.ver")])
def trazabilidad_lote_leche(request, pk):
    lote = LoteLeche.objects.filter(pk=pk).first()
    if lote is None:
        return Response({"detail": "No existe ese lote de leche."}, status=404)
    return Response({"lote_leche": lote.pk, "codigo": lote.codigo, "lotes_queso": servicios.usos_de_lote_leche(lote)})
