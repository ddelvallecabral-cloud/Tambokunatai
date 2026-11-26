from django.db import connection
from django.utils.dateparse import parse_date
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.cuentas.permisos import requiere_permiso

from .auditoria import verificar_cadena
from .models import Auditoria


@api_view(["GET"])
@permission_classes([AllowAny])
def salud(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"estado": "ok"})


class AuditoriaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre", default=None, read_only=True)

    class Meta:
        model = Auditoria
        fields = [
            "id", "fecha", "usuario", "usuario_nombre", "rol_activo", "accion", "entidad", "entidad_id",
            "cambios", "snapshot", "motivo", "ip", "dispositivo", "request_id", "registrado_offline_en",
        ]


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """Consulta de auditoría (solo Administrador). Filtros: accion, entidad, entidad_id, usuario, desde, hasta."""

    serializer_class = AuditoriaSerializer
    permission_classes = [requiere_permiso("auditoria.ver")]

    def get_queryset(self):
        qs = Auditoria.objects.select_related("usuario")
        p = self.request.query_params
        for campo in ("accion", "entidad", "entidad_id"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("usuario"):
            qs = qs.filter(usuario_id=p["usuario"])
        if p.get("desde") and parse_date(p["desde"]):
            qs = qs.filter(fecha__date__gte=parse_date(p["desde"]))
        if p.get("hasta") and parse_date(p["hasta"]):
            qs = qs.filter(fecha__date__lte=parse_date(p["hasta"]))
        return qs

    @action(detail=False, methods=["get"])
    def verificar(self, request):
        return Response(verificar_cadena())
