from decimal import Decimal

from rest_framework import serializers

from .models import CondicionCompra, Compra, CompraItem, CuentaPorPagar, Pago, Proveedor


class ProveedorSerializer(serializers.ModelSerializer):
    saldo_pendiente = serializers.IntegerField(read_only=True, default=0)
    ultima_compra = serializers.DateField(read_only=True, default=None)

    class Meta:
        model = Proveedor
        fields = ["id", "nombre", "tipo", "ruc", "contacto", "telefono", "email", "direccion", "notas", "activo",
                  "saldo_pendiente", "ultima_compra", "fecha_creacion"]
        read_only_fields = ["id", "fecha_creacion"]

    def validate_nombre(self, v):
        v = " ".join(v.split())
        repetido = Proveedor.objects.filter(nombre__iexact=v)
        if self.instance:
            repetido = repetido.exclude(pk=self.instance.pk)
        if repetido.exists():
            raise serializers.ValidationError("Ya hay un proveedor con ese nombre.")
        return v


class CompraItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    insumo_codigo = serializers.CharField(source="insumo.codigo", read_only=True)
    unidad = serializers.CharField(source="insumo.unidad", read_only=True)

    class Meta:
        model = CompraItem
        fields = ["insumo", "insumo_nombre", "insumo_codigo", "unidad", "cantidad", "precio_unitario", "subtotal",
                  "lote_proveedor"]


class PagoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = ["id", "fecha", "monto", "medio", "referencia", "usuario_nombre", "anulado", "motivo_anulacion"]


class CuentaPagarSerializer(serializers.ModelSerializer):
    saldo = serializers.IntegerField(read_only=True)
    pagos = PagoSerializer(many=True, read_only=True)
    compra_codigo = serializers.CharField(source="compra.codigo", read_only=True)
    factura = serializers.CharField(source="compra.factura", read_only=True)
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)

    class Meta:
        model = CuentaPorPagar
        fields = ["id", "compra", "compra_codigo", "factura", "proveedor", "proveedor_nombre", "monto", "pagado",
                  "saldo", "fecha_emision", "vencimiento", "estado", "pagos"]


class CompraSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(read_only=True)
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)
    items = CompraItemSerializer(many=True, read_only=True)
    cuenta = CuentaPagarSerializer(read_only=True)
    tiene_comprobante = serializers.SerializerMethodField()
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)

    class Meta:
        model = Compra
        fields = ["id", "codigo", "numero", "fecha", "proveedor", "proveedor_nombre", "factura", "condicion", "total",
                  "observaciones", "estado_compra", "motivo_estado", "items", "cuenta", "tiene_comprobante",
                  "creado_por_nombre", "fecha_creacion"]

    def get_tiene_comprobante(self, obj):
        return bool(obj.comprobante)


class ItemEntradaSerializer(serializers.Serializer):
    insumo = serializers.UUIDField()
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    precio_unitario = serializers.IntegerField(min_value=1)
    lote_proveedor = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)


class RegistrarCompraSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    proveedor = serializers.UUIDField()
    fecha = serializers.DateField(required=False)
    factura = serializers.CharField(required=False, allow_blank=True, default="", max_length=40)
    condicion = serializers.ChoiceField(choices=CondicionCompra.choices, default=CondicionCompra.CONTADO)
    pagada = serializers.BooleanField(default=False)
    medio = serializers.ChoiceField(choices=["efectivo", "transferencia", "cheque", "otro"], default="efectivo")
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")
    items = ItemEntradaSerializer(many=True)


class PagoEntradaSerializer(serializers.Serializer):
    monto = serializers.IntegerField(min_value=1)
    fecha = serializers.DateField(required=False)
    medio = serializers.ChoiceField(choices=["efectivo", "transferencia", "cheque", "otro"], default="efectivo")
    referencia = serializers.CharField(required=False, allow_blank=True, default="", max_length=80)


