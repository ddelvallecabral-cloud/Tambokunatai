from decimal import Decimal

from rest_framework import serializers

from .models import Cliente, Cobro, CuentaPorCobrar, MedioPago, Precio, Producto, Venta, VentaLote


class ClienteSerializer(serializers.ModelSerializer):
    saldo_pendiente = serializers.IntegerField(read_only=True, default=0)
    ultima_compra = serializers.DateField(read_only=True, default=None)

    class Meta:
        model = Cliente
        fields = ["id", "nombre", "tipo", "documento", "telefono", "email", "direccion", "condicion_pago",
                  "activo", "notas", "saldo_pendiente", "ultima_compra", "fecha_creacion"]
        read_only_fields = ["id", "fecha_creacion"]

    def validate_nombre(self, v):
        return " ".join(v.split())


class PrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Precio
        fields = ["id", "producto", "tipo_cliente", "cantidad_minima", "precio_unitario", "activo",
                  "fecha_modificacion"]
        read_only_fields = ["id", "fecha_modificacion"]
        validators = []  # la unicidad se valida abajo, con un mensaje claro

    def validate(self, datos):
        actual = self.instance
        valor = lambda k: datos.get(k, getattr(actual, k, None) if actual else None)  # noqa: E731
        if valor("activo") is not False:
            repetido = Precio.objects.filter(activo=True, producto=valor("producto"), tipo_cliente=valor("tipo_cliente") or "",
                                             cantidad_minima=valor("cantidad_minima") or 0)
            if actual:
                repetido = repetido.exclude(pk=actual.pk)
            if repetido.exists():
                raise serializers.ValidationError("Ya hay un precio activo para ese producto, tipo de cliente y cantidad mínima.")
        return datos


class VentaLoteSerializer(serializers.ModelSerializer):
    codigo = serializers.SerializerMethodField()
    lote = serializers.SerializerMethodField()
    tipo = serializers.SerializerMethodField()

    class Meta:
        model = VentaLote
        fields = ["lote", "codigo", "tipo", "cantidad"]

    def get_lote(self, o):
        return o.lote_queso_id or o.lote_leche_id

    def get_codigo(self, o):
        return (o.lote_queso or o.lote_leche).codigo

    def get_tipo(self, o):
        return "queso" if o.lote_queso_id else "leche"


class CobroSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre", default=None, read_only=True)

    class Meta:
        model = Cobro
        fields = ["id", "fecha", "monto", "medio", "referencia", "usuario_nombre", "anulado", "motivo_anulacion",
                  "fecha_creacion"]


class CuentaSerializer(serializers.ModelSerializer):
    saldo = serializers.IntegerField(read_only=True)
    cobros = CobroSerializer(many=True, read_only=True)
    venta_codigo = serializers.CharField(source="venta.codigo", read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)

    class Meta:
        model = CuentaPorCobrar
        fields = ["id", "venta", "venta_codigo", "cliente", "cliente_nombre", "monto", "cobrado", "saldo",
                  "fecha_emision", "vencimiento", "estado", "cobros"]


class CuentaResumenSerializer(serializers.ModelSerializer):
    saldo = serializers.IntegerField(read_only=True)

    class Meta:
        model = CuentaPorCobrar
        fields = ["id", "monto", "cobrado", "saldo", "vencimiento", "estado"]


class VentaSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(read_only=True)
    unidad = serializers.CharField(read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    cliente_tipo = serializers.CharField(source="cliente.tipo", read_only=True)
    lotes = VentaLoteSerializer(many=True, read_only=True)
    cuenta = CuentaResumenSerializer(read_only=True)
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)

    class Meta:
        model = Venta
        fields = ["id", "codigo", "numero", "fecha", "cliente", "cliente_nombre", "cliente_tipo", "producto",
                  "unidad", "cantidad", "precio_unitario", "precio_de_lista", "total", "estado_venta",
                  "fecha_entrega", "observaciones", "lotes", "cuenta", "motivo_estado", "creado_por_nombre",
                  "fecha_creacion"]


class LotePedidoSerializer(serializers.Serializer):
    lote = serializers.UUIDField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))


class RegistrarVentaSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    cliente = serializers.UUIDField()
    producto = serializers.ChoiceField(choices=Producto.choices)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    fecha = serializers.DateField(required=False)
    precio_unitario = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    lotes = LotePedidoSerializer(many=True, required=False, allow_null=True)
    entregada = serializers.BooleanField(default=False)
    cobrar_ahora = serializers.BooleanField(default=False)
    medio = serializers.ChoiceField(choices=MedioPago.choices, default=MedioPago.EFECTIVO)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")


class CobroEntradaSerializer(serializers.Serializer):
    monto = serializers.IntegerField(min_value=1)
    fecha = serializers.DateField(required=False)
    medio = serializers.ChoiceField(choices=MedioPago.choices, default=MedioPago.EFECTIVO)
    referencia = serializers.CharField(required=False, allow_blank=True, default="")
