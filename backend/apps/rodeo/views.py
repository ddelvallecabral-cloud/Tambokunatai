from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.core.contexto import fijar_usuario
from apps.core.mixins import EstadoRegistro
from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso
from apps.leche import servicios as leche
from apps.leche.models import Ordene
from apps.leche.serializers import LoteLecheSerializer

from . import servicios
from .models import Animal
from .serializers import AnimalSerializer, RegistrarOrdeneSerializer


class AnimalViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Plantel. Filtros: situacion, buscar (caravana o nombre), incluir_bajas=1."""

    serializer_class = AnimalSerializer
    http_method_names = ["get", "post", "patch"]
    PERMISOS = {"list": "rodeo.ver", "retrieve": "rodeo.ver", "produccion": "rodeo.ver",
                "create": "rodeo.animal.gestionar", "partial_update": "rodeo.animal.gestionar"}
    PERMISO_POR_DEFECTO = "rodeo.animal.gestionar"

    def get_queryset(self):
        qs = Animal.objects.exclude(estado=EstadoRegistro.ANULADO)
        p = self.request.query_params
        if self.action == "list":
            if p.get("situacion"):
                qs = qs.filter(situacion=p["situacion"])
            elif p.get("incluir_bajas") != "1":
                qs = qs.exclude(situacion__in=["vendida", "muerta"])
            if p.get("buscar"):
                from django.db.models import Q
                qs = qs.filter(Q(caravana__icontains=p["buscar"]) | Q(nombre__icontains=p["buscar"]))
        return qs.order_by("caravana")

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        if self.action in ("list", "retrieve"):
            contexto["produccion"] = servicios.produccion_por_animal()
        return contexto

    @action(detail=True, methods=["get"])
    def produccion(self, request, pk=None):
        animal = self.get_object()
        dias = min(max(int(request.query_params.get("dias", 30)), 7), 120)
        return Response({
            **servicios.produccion_por_animal(animales=[animal]).get(animal.pk, {}),
            "serie": servicios.serie_animal(animal, dias),
        })


@api_view(["GET", "POST"])
@permission_classes([requiere_permiso("rodeo.ver")])
def ordene(request):
    """GET ?fecha&ordene: planilla de la sesión. POST: guarda la planilla completa."""
    fijar_usuario(request.user)
    if request.method == "GET":
        fecha = fecha_param(request.query_params.get("fecha")) or leche.hoy()
        sesion = request.query_params.get("ordene") or Ordene.MANANA
        if sesion not in Ordene.values:
            return Response({"ordene": "Usá manana o tarde."}, status=400)
        return Response(servicios.planilla(fecha, sesion))

    if not request.user.tiene_permiso("rodeo.ordene.registrar", "leche.lote.gestionar"):
        return Response({"detail": "No tenés permiso para esta acción."}, status=403)
    datos = RegistrarOrdeneSerializer(data=request.data)
    datos.is_valid(raise_exception=True)
    resultado = servicios.registrar_ordene(request.user, **datos.validated_data)
    lote = leche.con_totales(type(resultado["lote"]).objects.filter(pk=resultado["lote"].pk)).get()
    return Response({
        "lote": LoteLecheSerializer(lote).data,
        "creado": resultado["creado"], "total": resultado["total"],
        "total_anterior": resultado["total_anterior"], "vacas_cambiadas": resultado["vacas_cambiadas"],
    }, status=status.HTTP_201_CREATED if resultado["creado"] else status.HTTP_200_OK)
