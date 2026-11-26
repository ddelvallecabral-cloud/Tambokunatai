from decimal import Decimal

from rest_framework import serializers

from .models import LoteQueso, LoteQuesoInsumo, LoteQuesoLeche


class OrigenSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="lote_leche.codigo", read_only=True)
    fecha = serializers.DateField(source="lote_leche.fecha", read_only=True)
    ordene = serializers.CharField(source="lote_leche.ordene", read_only=True)
    vigente = serializers.SerializerMethodField()

    class Meta:
        model = LoteQuesoLeche
        fields = ["lote_leche", "codigo", "fecha", "ordene", "litros", "vigente"]

    def get_vigente(self, obj):
        return obj.destino_id is not None


class UsoInsumoSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    unidad = serializers.CharField(source="insumo.unidad", read_only=True)

    class Meta:
        model = LoteQuesoInsumo
        fields = ["insumo", "nombre", "unidad", "cantidad_declarada", "cantidad_consumida"]


class LoteQuesoSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(read_only=True)
    kg_netos = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    origenes = OrigenSerializer(many=True, read_only=True)
    insumos = UsoInsumoSerializer(many=True, read_only=True)
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)
    cerrado_por_nombre = serializers.CharField(source="cerrado_por.nombre", default=None, read_only=True)
    aprobado_por_nombre = serializers.CharField(source="aprobado_por.nombre", default=None, read_only=True)

    class Meta:
        model = LoteQueso
        fields = ["id", "codigo", "numero", "fecha", "litros_leche", "kg_obtenidos", "merma_kg", "kg_netos",
                  "rendimiento_l_kg", "rendimiento_fuera_de_rango", "observaciones", "estado", "motivo_estado",
                  "origenes", "insumos", "creado_por", "creado_por_nombre", "fecha_creacion", "cerrado_por_nombre",
                  "fecha_cierre", "aprobado_por_nombre", "fecha_aprobacion", "version"]


class OrigenEntradaSerializer(serializers.Serializer):
    lote_leche = serializers.UUIDField()
    litros = serializers.DecimalField(max_digits=9, decimal_places=1, min_value=Decimal("0.1"))


class InsumoEntradaSerializer(serializers.Serializer):
    insumo = serializers.UUIDField()
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"))


class IniciarLoteSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    fecha = serializers.DateField()
    origenes = OrigenEntradaSerializer(many=True)
    insumos = InsumoEntradaSerializer(many=True, required=False, default=list)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")


class CerrarLoteSerializer(serializers.Serializer):
    kg_obtenidos = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"),
                                            required=False, allow_null=True)
    merma_kg = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0"), default=Decimal("0"))
    consumos = InsumoEntradaSerializer(many=True, required=False, allow_null=True, default=None)
    observaciones = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


class ComentarioSerializer(serializers.Serializer):
    comentario = serializers.CharField(required=False, allow_blank=True, default="")
