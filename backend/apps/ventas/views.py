from django.db.models import Max, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.core.mixins import EstadoRegistro, ReglaNegocio
from apps.core.vistas import PermisosPorAccion, fecha_param
from apps.cuentas.permisos import requiere_permiso

from . import servicios
from .models import Cliente, Cobro, CuentaPorCobrar, EstadoCuenta, EstadoVenta, Precio, Producto, Venta
from .serializers import (
    ClienteSerializer, CobroEntradaSerializer, CuentaSerializer, PrecioSerializer, RegistrarVentaSerializer,
    VentaSerializer,
)


class ClienteViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Clientes. Filtros: buscar (nombre, documento o teléfono), tipo, activo=0|1."""

    serializer_class = ClienteSerializer
    http_method_names = ["get", "post", "patch"]
    PERMISOS = {"list": "ventas.ver", "retrieve": "ventas.ver", "historial": "ventas.ver",
                "create": "ventas.cliente.gestionar", "partial_update": "ventas.cliente.gestionar"}
    PERMISO_POR_DEFECTO = "ventas.cliente.gestionar"

    def get_queryset(self):
        abiertas = CuentaPorCobrar.objects.filter(cliente=OuterRef("pk"), estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL])
        qs = Cliente.objects.exclude(estado=EstadoRegistro.ANULADO).annotate(
            saldo_pendiente=Coalesce(Subquery(
                abiertas.values("cliente").annotate(t=Sum("monto") - Sum("cobrado")).values("t")[:1]), Value(0)),
            ultima_compra=Max("ventas__fecha", filter=~Q(ventas__estado_venta=EstadoVenta.ANULADA)),
        )
        p = self.request.query_params
        if self.action == "list":
            if p.get("buscar"):
                t = p["buscar"].strip()
                qs = qs.filter(Q(nombre__icontains=t) | Q(documento__icontains=t) | Q(telefono__icontains=t))
            if p.get("tipo"):
                qs = qs.filter(tipo=p["tipo"])
            if p.get("activo") in ("0", "1"):
                qs = qs.filter(activo=p["activo"] == "1")
        return qs.order_by("nombre")

    def create(self, request, *args, **kwargs):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        cliente = datos.save()
        return Response(ClienteSerializer(self.get_queryset().get(pk=cliente.pk)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        cliente = Cliente.objects.get(pk=kwargs["pk"])
        datos = self.get_serializer(cliente, data=request.data, partial=True)
        datos.is_valid(raise_exception=True)
        datos.save()
        return Response(ClienteSerializer(self.get_queryset().get(pk=cliente.pk)).data)

    @action(detail=True, methods=["get"])
    def historial(self, request, pk=None):
        cliente = self.get_object()
        h = servicios.historial_cliente(cliente)
        return Response({
            "cliente": ClienteSerializer(cliente).data,
            "totales": h["totales"],
            "lotes_entregados": h["lotes_entregados"],
            "ventas": VentaSerializer(h["ventas"], many=True).data,
        })


class PrecioViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    """Tabla de precios. Todos los que venden la ven; solo el Administrador la cambia."""

    serializer_class = PrecioSerializer
    http_method_names = ["get", "post", "patch"]
    PERMISOS = {"list": "ventas.ver", "cotizar": "ventas.ver"}
    PERMISO_POR_DEFECTO = "ventas.precio.gestionar"
    pagination_class = None

    def get_queryset(self):
        qs = Precio.objects.all()
        if self.request.query_params.get("todos") != "1":
            qs = qs.filter(activo=True)
        return qs.order_by("producto", "tipo_cliente", "cantidad_minima")

    @action(detail=False, methods=["get"])
    def cotizar(self, request):
        """?cliente=&producto=&cantidad= → precio de lista, total, stock disponible y lotes que saldrían."""
        p = request.query_params
        producto = p.get("producto", Producto.QUESO)
        cliente = Cliente.objects.filter(pk=p.get("cliente")).first() if p.get("cliente") else None
        try:
            cantidad = servicios.Decimal(p.get("cantidad") or "0")
        except Exception:
            cantidad = servicios.CERO
        disponibles = servicios.stock_vendible(producto)
        stock = sum((d["disponible"] for d in disponibles), servicios.CERO)
        respuesta = {"producto": producto, "stock_disponible": stock,
                     "lotes_disponibles": [{k: d[k] for k in ("id", "codigo", "fecha", "disponible")} for d in disponibles]}
        try:
            precio, fila = servicios.precio_para(cliente.tipo if cliente else "", producto, max(cantidad, servicios.CERO))
            respuesta.update({"precio_unitario": precio, "regla": PrecioSerializer(fila).data,
                              "total": servicios.calcular_total(cantidad, precio) if cantidad > 0 else 0})
        except ReglaNegocio as e:
            respuesta.update({"precio_unitario": None, "total": None, "error_precio": str(e)})
        return Response(respuesta)


class VentaViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Ventas. Filtros: desde, hasta, cliente, producto, estado_venta, lote_queso."""

    serializer_class = VentaSerializer
    PERMISOS = {"list": "ventas.ver", "retrieve": "ventas.ver",
                "create": "ventas.venta.registrar", "entregar": "ventas.venta.registrar",
                "cobrar": "ventas.cobro.registrar", "anular": "ventas.venta.aprobar"}
    PERMISO_POR_DEFECTO = "ventas.venta.aprobar"

    def get_queryset(self):
        qs = Venta.objects.select_related("cliente", "cuenta", "creado_por").prefetch_related(
            "lotes__lote_queso", "lotes__lote_leche")
        if self.action != "list":
            return qs
        p = self.request.query_params
        if desde := fecha_param(p.get("desde"), "desde"):
            qs = qs.filter(fecha__gte=desde)
        if hasta := fecha_param(p.get("hasta"), "hasta"):
            qs = qs.filter(fecha__lte=hasta)
        for campo in ("cliente", "producto", "estado_venta"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("lote_queso"):
            qs = qs.filter(lotes__lote_queso=p["lote_queso"]).distinct()
        if p.get("buscar"):
            qs = qs.filter(cliente__nombre__icontains=p["buscar"])
        return qs.order_by("-fecha", "-numero")

    def _respuesta(self, venta, codigo=status.HTTP_200_OK):
        return Response(VentaSerializer(self.get_queryset().get(pk=venta.pk)).data, status=codigo)

    def create(self, request):
        datos = RegistrarVentaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        venta, creada = servicios.registrar_venta(request.user, **datos.validated_data)
        return self._respuesta(venta, status.HTTP_201_CREATED if creada else status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def entregar(self, request, pk=None):
        return self._respuesta(servicios.entregar(request.user, self.get_object()))

    @action(detail=True, methods=["post"])
    def cobrar(self, request, pk=None):
        venta = self.get_object()
        datos = CobroEntradaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        servicios.registrar_cobro(request.user, venta.cuenta, **datos.validated_data)
        return self._respuesta(venta, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        return self._respuesta(servicios.anular_venta(request.user, self.get_object(), str(request.data.get("motivo", ""))))


class CuentaViewSet(PermisosPorAccion, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cuentas por cobrar (vista global: solo quien ve los reportes financieros, el Administrador).
    Filtros: estado (abiertas = pendiente o parcial), cliente, vencidas=1."""

    serializer_class = CuentaSerializer
    PERMISOS = {"anular_cobro": "ventas.venta.aprobar"}
    PERMISO_POR_DEFECTO = "reportes.financieros"

    def get_queryset(self):
        qs = CuentaPorCobrar.objects.select_related("venta", "cliente").prefetch_related("cobros__usuario")
        p = self.request.query_params
        if self.action == "list":
            estado = p.get("estado", "abiertas")
            if estado == "abiertas":
                qs = qs.filter(estado__in=[EstadoCuenta.PENDIENTE, EstadoCuenta.PARCIAL])
            elif estado != "todas":
                qs = qs.filter(estado=estado)
            if p.get("cliente"):
                qs = qs.filter(cliente=p["cliente"])
            if p.get("vencidas") == "1":
                qs = qs.filter(vencimiento__lt=servicios.hoy())
        return qs.order_by("vencimiento", "fecha_emision")

    @action(detail=False, methods=["post"], url_path=r"cobros/(?P<cobro_id>[0-9a-f-]+)/anular")
    def anular_cobro(self, request, cobro_id=None):
        cobro = Cobro.objects.filter(pk=cobro_id).first()
        if cobro is None:
            return Response({"detail": "No existe ese cobro."}, status=404)
        servicios.anular_cobro(request.user, cobro, str(request.data.get("motivo", "")))
        return Response(CuentaSerializer(self.get_queryset().get(pk=cobro.cuenta_id)).data)


@api_view(["GET"])
@permission_classes([requiere_permiso("reportes.financieros")])
def resumen_cuentas(request):
    return Response(servicios.resumen_cuentas(fecha_param(request.query_params.get("fecha"))))
