from django.db.models import Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.core import archivos
from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso

from . import servicios
from .models import Compra, CuentaPorPagar, EstadoCompra, EstadoCuentaPagar, Pago, Proveedor
from .serializers import (
    CompraSerializer, CuentaPagarSerializer, PagoEntradaSerializer, ProveedorSerializer, RegistrarCompraSerializer,
)


class ProveedorViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Proveedores. Filtros: buscar, tipo, activo=0|1."""

    serializer_class = ProveedorSerializer
    http_method_names = ["get", "post", "patch"]
    PERMISOS = {"list": "compras.ver", "retrieve": "compras.ver"}
    PERMISO_POR_DEFECTO = "compras.compra.registrar"

    def get_queryset(self):
        abiertas = CuentaPorPagar.objects.filter(proveedor=OuterRef("pk"),
                                                 estado__in=[EstadoCuentaPagar.PENDIENTE, EstadoCuentaPagar.PARCIAL])
        qs = Proveedor.objects.exclude(estado=EstadoRegistro.ANULADO).annotate(
            saldo_pendiente=Coalesce(Subquery(
                abiertas.values("proveedor").annotate(t=Sum("monto") - Sum("pagado")).values("t")[:1]), Value(0)),
            ultima_compra=Max("compras__fecha", filter=Q(compras__estado_compra=EstadoCompra.CONFIRMADA)),
        )
        p = self.request.query_params
        if self.action == "list":
            if p.get("buscar"):
                t = p["buscar"].strip()
                qs = qs.filter(Q(nombre__icontains=t) | Q(ruc__icontains=t) | Q(contacto__icontains=t))
            if p.get("tipo"):
                qs = qs.filter(tipo=p["tipo"])
            if p.get("activo") in ("0", "1"):
                qs = qs.filter(activo=p["activo"] == "1")
        return qs.order_by("nombre")

    def create(self, request, *args, **kwargs):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        p = datos.save()
        return Response(ProveedorSerializer(self.get_queryset().get(pk=p.pk)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        p = Proveedor.objects.get(pk=kwargs["pk"])
        datos = self.get_serializer(p, data=request.data, partial=True)
        datos.is_valid(raise_exception=True)
        datos.save()
        return Response(ProveedorSerializer(self.get_queryset().get(pk=p.pk)).data)


class CompraViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Compras de insumos. Filtros: desde, hasta, proveedor, insumo, estado_compra."""

    serializer_class = CompraSerializer
    PERMISOS = {"list": "compras.ver", "retrieve": "compras.ver", "comprobante": "compras.ver",
                "create": "compras.compra.registrar", "subir_comprobante": "compras.compra.registrar",
                "pagar": "compras.pago.registrar", "anular": "compras.compra.aprobar"}
    PERMISO_POR_DEFECTO = "compras.compra.aprobar"

    def get_queryset(self):
        qs = Compra.objects.select_related("proveedor", "cuenta", "creado_por").prefetch_related(
            "items__insumo", "cuenta__pagos__usuario")
        if self.action != "list":
            return qs
        p = self.request.query_params
        if desde := fecha_param(p.get("desde"), "desde"):
            qs = qs.filter(fecha__gte=desde)
        if hasta := fecha_param(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__lte=hasta)
        for campo in ("proveedor", "estado_compra"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("insumo"):
            qs = qs.filter(items__insumo=p["insumo"]).distinct()
        return qs.order_by("-fecha", "-numero")

    def _respuesta(self, compra, codigo=status.HTTP_200_OK):
        return Response(CompraSerializer(self.get_queryset().get(pk=compra.pk)).data, status=codigo)

    def create(self, request):
        datos = RegistrarCompraSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        compra, creada = servicios.registrar_compra(request.user, **datos.validated_data)
        return self._respuesta(compra, status.HTTP_201_CREATED if creada else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="comprobante")
    def subir_comprobante(self, request, pk=None):
        compra = self.get_object()
        if compra.estado_compra == EstadoCompra.ANULADA:
            raise ReglaNegocio("La compra está anulada.")
        archivo = request.FILES.get("comprobante")
        if not archivo:
            raise ReglaNegocio("Elegí la foto o el PDF del comprobante.")
        compra._tipo_comprobante = archivos.validar_comprobante(archivo)
        compra.comprobante = archivo
        compra.save()
        return self._respuesta(compra)

    @subir_comprobante.mapping.get
    def comprobante(self, request, pk=None):
        compra = self.get_object()
        if not compra.comprobante:
            raise Http404
        return archivos.entregar(compra.comprobante, f"comprobante-{compra.codigo}")

    @action(detail=True, methods=["post"])
    def pagar(self, request, pk=None):
        compra = self.get_object()
        datos = PagoEntradaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        servicios.registrar_pago(request.user, compra.cuenta, **datos.validated_data)
        return self._respuesta(compra, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        return self._respuesta(servicios.anular_compra(request.user, self.get_object(), str(request.data.get("motivo", ""))))


class CuentaPagarViewSet(PermisosPorAccion, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Cuentas por pagar (Administrador). Filtros: estado (abiertas por defecto), proveedor, vencidas=1."""

    serializer_class = CuentaPagarSerializer
    PERMISO_POR_DEFECTO = "compras.pago.registrar"

    def get_queryset(self):
        qs = CuentaPorPagar.objects.select_related("compra", "proveedor").prefetch_related("pagos__usuario")
        p = self.request.query_params
        estado = p.get("estado", "abiertas")
        if estado == "abiertas":
            qs = qs.filter(estado__in=[EstadoCuentaPagar.PENDIENTE, EstadoCuentaPagar.PARCIAL])
        elif estado != "todas":
            qs = qs.filter(estado=estado)
        if p.get("proveedor"):
            qs = qs.filter(proveedor=p["proveedor"])
        if p.get("vencidas") == "1":
            qs = qs.filter(vencimiento__lt=servicios.hoy())
        return qs.order_by("vencimiento")

    @action(detail=False, methods=["post"], url_path=r"pagos/(?P<pago_id>[0-9a-f-]+)/anular")
    def anular_pago(self, request, pago_id=None):
        pago = Pago.objects.filter(pk=pago_id).first()
        if pago is None:
            raise Http404
        servicios.anular_pago(request.user, pago, str(request.data.get("motivo", "")))
        return Response(CuentaPagarSerializer(CuentaPorPagar.objects.get(pk=pago.cuenta_id)).data)


@api_view(["GET"])
@permission_classes([requiere_permiso("compras.pago.registrar")])
def resumen_cuentas(request):
    return Response(servicios.resumen_cuentas(fecha_param(request.query_params.get("fecha"))))
