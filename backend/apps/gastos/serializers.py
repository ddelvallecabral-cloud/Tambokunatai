from rest_framework import serializers

from .models import Categoria, CentroCosto, Gasto


class GastoSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", default=None, read_only=True)
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)
    aprobado_por_nombre = serializers.CharField(source="aprobado_por.nombre", default=None, read_only=True)
    tiene_comprobante = serializers.SerializerMethodField()
    tipo_comprobante = serializers.SerializerMethodField()

    class Meta:
        model = Gasto
        fields = ["id", "fecha", "categoria", "centro_costo", "monto", "descripcion", "proveedor", "proveedor_nombre",
                  "comprobante_numero", "tiene_comprobante", "tipo_comprobante", "estado", "motivo_estado",
                  "aprobacion_automatica", "creado_por", "creado_por_nombre", "fecha_creacion",
                  "aprobado_por_nombre", "fecha_aprobacion"]

    def get_tiene_comprobante(self, obj):
        return bool(obj.comprobante)

    def get_tipo_comprobante(self, obj):
        if not obj.comprobante:
            return None
        return "pdf" if obj.comprobante.name.lower().endswith(".pdf") else "imagen"


class GastoEntradaSerializer(serializers.Serializer):
    """Alta o corrección. Llega como formulario (multipart) para poder traer la foto del comprobante."""

    id = serializers.UUIDField(required=False)
    fecha = serializers.DateField(required=False)
    categoria = serializers.ChoiceField(choices=Categoria.choices)
    centro_costo = serializers.ChoiceField(choices=CentroCosto.choices)
    monto = serializers.IntegerField(min_value=1)
    descripcion = serializers.CharField(max_length=255)
    proveedor = serializers.UUIDField(required=False, allow_null=True)
    comprobante_numero = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)
    comprobante = serializers.FileField(required=False, allow_null=True)

    def validate_proveedor(self, v):
        if v is None:
            return None
        from apps.compras.models import Proveedor
        p = Proveedor.objects.filter(pk=v).first()
        if p is None:
            raise serializers.ValidationError("El proveedor no existe.")
        return p
