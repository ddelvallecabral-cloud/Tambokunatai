import datetime

from django.db.models import Exists, F, OuterRef, Prefetch
from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.contexto import fijar_usuario
from apps.core.mixins import TransicionInvalida
from apps.cuentas.permisos import requiere_permiso

from . import servicios
from .models import DESTINO_PENDIENTE, DestinoLeche, LoteLeche
from .serializers import (
    AsignarDestinoSerializer,
    CrearLoteSerializer,
    EditarLoteSerializer,
    LoteLecheSerializer,
    MotivoSerializer,
)


def _fecha(valor, nombre):
    if not valor:
        return None
    fecha = parse_date(valor)
    if fecha is None:
        raise ValidationError({nombre: "Fecha inválida, usá AAAA-MM-DD."})
    return fecha


def _regla(funcion, *args, **kwargs):
    """Ejecuta un servicio y traduce sus errores de negocio a 409 con mensaje legible."""
    try:
        return funcion(*args, **kwargs)
    except (servicios.ReglaNegocio, TransicionInvalida) as error:
        raise _Conflicto(str(error))


class _Conflicto(Exception):
    pass


class LoteLecheViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Lotes de leche. Filtros del listado: desde, hasta, fecha, ordene, destino, estado."""

    serializer_class = LoteLecheSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    PERMISOS = {
        "list": "leche.ver", "retrieve": "leche.ver", "resumen": "leche.ver",
        "create": "leche.lote.gestionar", "partial_update": "leche.lote.gestionar",
        "destinos": "leche.lote.gestionar", "quitar_destino": "leche.lote.gestionar",
        "cerrar": "leche.lote.cerrar",
        "aprobar": "leche.lote.aprobar", "rechazar": "leche.lote.aprobar",
        "reabrir": "leche.lote.aprobar", "anular": "leche.lote.aprobar",
    }

    def get_permissions(self):
        return [requiere_permiso(self.PERMISOS.get(self.action, "leche.lote.aprobar"))()]

    def handle_exception(self, exc):
        if isinstance(exc, _Conflicto):
            return Response({"detail": str(exc), "codigo": "regla_de_negocio"}, status=status.HTTP_409_CONFLICT)
        return super().handle_exception(exc)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        fijar_usuario(request.user)

    def get_queryset(self):
        qs = servicios.con_totales(LoteLeche.objects.all()).select_related(
            "creado_por", "aprobado_por", "propuesto_por"
        ).prefetch_related(Prefetch("destinos", queryset=DestinoLeche.objects.select_related("creado_por")))
        if self.action != "list":
            return qs
        p = self.request.query_params
        if fecha := _fecha(p.get("fecha"), "fecha"):
            qs = qs.filter(fecha=fecha)
        if desde := _fecha(p.get("desde"), "desde"):
            qs = qs.filter(fecha__gte=desde)
        if hasta := _fecha(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__lte=hasta)
        if p.get("ordene"):
            qs = qs.filter(ordene=p["ordene"])
        if p.get("estado"):
            qs = qs.filter(estado=p["estado"])
        else:
            qs = qs.exclude(estado="anulado")
        destino = p.get("destino")
        if destino == DESTINO_PENDIENTE:
            qs = qs.filter(_asignados__lt=F("litros"))
        elif destino:
            qs = qs.filter(Exists(DestinoLeche.objects.filter(lote=OuterRef("pk"), tipo=destino)))
        return qs.order_by("-fecha", "-ordene")

    def _respuesta(self, lote, codigo=status.HTTP_200_OK, **extra):
        lote = self.get_queryset().get(pk=lote.pk)
        return Response({**LoteLecheSerializer(lote).data, **extra}, status=codigo)

    def create(self, request):
        datos = CrearLoteSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        lote, creado = _regla(servicios.crear_lote, request.user, **datos.validated_data)
        return self._respuesta(lote, status.HTTP_201_CREATED if creado else status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        lote = self.get_object()
        datos = EditarLoteSerializer(data=request.data, partial=True)
        datos.is_valid(raise_exception=True)
        cambios = dict(datos.validated_data)
        motivo = cambios.pop("motivo", "")
        resultado = _regla(servicios.editar_lote, request.user, lote, cambios, motivo)
        return self._respuesta(lote, resultado=resultado)

    @action(detail=True, methods=["post"])
    def destinos(self, request, pk=None):
        lote = self.get_object()
        datos = AsignarDestinoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        _regla(servicios.asignar_destino, request.user, lote, **datos.validated_data)
        return self._respuesta(lote, status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"destinos/(?P<destino_id>[0-9a-f-]+)")
    def quitar_destino(self, request, pk=None, destino_id=None):
        lote = self.get_object()
        destino = lote.destinos.filter(pk=destino_id).first()
        if destino is None:
            return Response({"detail": "Ese destino no existe en este lote."}, status=status.HTTP_404_NOT_FOUND)
        _regla(servicios.quitar_destino, request.user, destino, request.data.get("motivo", ""))
        return self._respuesta(lote)

    def _motivo(self, request):
        datos = MotivoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        return datos.validated_data["motivo"]

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        lote = _regla(servicios.aprobar_correccion, request.user, self.get_object())
        return self._respuesta(lote)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        lote = _regla(servicios.rechazar_correccion, request.user, self.get_object(), self._motivo(request))
        return self._respuesta(lote)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        lote = _regla(servicios.cerrar_lote, request.user, self.get_object())
        return self._respuesta(lote)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        lote = self.get_object()
        _regla(lote.reabrir, self._motivo(request))
        return self._respuesta(lote)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        lote = _regla(servicios.anular_lote, request.user, self.get_object(), self._motivo(request))
        return self._respuesta(lote)

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        fecha = _fecha(request.query_params.get("fecha"), "fecha") or servicios.hoy()
        return Response(servicios.resumen_dia(fecha))


@api_view(["GET"])
@permission_classes([requiere_permiso("leche.ver")])
def tablero(request):
    fecha = _fecha(request.query_params.get("fecha"), "fecha")
    return Response(servicios.tablero(fecha))
