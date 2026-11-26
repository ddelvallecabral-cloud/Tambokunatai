from decimal import Decimal

from rest_framework import serializers

from .models import Insumo, Motivo, MovimientoInventario


class InsumoSerializer(serializers.ModelSerializer):
    stock = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    reservado = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    disponible = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    bajo_minimo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Insumo
        fields = ["id", "codigo", "nombre", "categoria", "unidad", "stock_minimo", "activo",
                  "stock", "reservado", "disponible", "bajo_minimo", "fecha_creacion", "fecha_modificacion"]
        read_only_fields = ["id", "fecha_creacion", "fecha_modificacion"]

    def validate_codigo(self, valor):
        return valor.strip().upper()


class MovimientoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", default=None, read_only=True)
    lote_leche_codigo = serializers.CharField(source="lote_leche.codigo", default=None, read_only=True)
    lote_queso_codigo = serializers.CharField(source="lote_queso.codigo", default=None, read_only=True)
    usuario_nombre = serializers.CharField(source="usuario.nombre", default=None, read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = ["id", "fecha", "item", "tipo", "motivo", "cantidad", "unidad", "insumo", "insumo_nombre",
                  "lote_leche", "lote_leche_codigo", "lote_queso", "lote_queso_codigo", "lote_proveedor",
                  "nota", "usuario_nombre"]


class EntradaSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    motivo = serializers.ChoiceField(choices=[Motivo.COMPRA, Motivo.AJUSTE], default=Motivo.COMPRA)
    lote_proveedor = serializers.CharField(required=False, allow_blank=True, default="")
    nota = serializers.CharField(required=False, allow_blank=True, default="")


class SalidaAjusteSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    nota = serializers.CharField()
