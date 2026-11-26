from decimal import Decimal

from rest_framework import serializers

from .models import DESTINO_PENDIENTE, DestinoLeche, LoteLeche, Ordene, TipoDestino

OPCIONES_DESTINO = [DESTINO_PENDIENTE, *TipoDestino.values]


class DestinoSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)

    class Meta:
        model = DestinoLeche
        fields = ["id", "tipo", "litros", "nota", "creado_por_nombre", "fecha_creacion"]
        read_only_fields = ["id", "creado_por_nombre", "fecha_creacion"]


class LoteLecheSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(read_only=True)
    destino = serializers.CharField(read_only=True)
    litros_asignados = serializers.DecimalField(max_digits=9, decimal_places=1, read_only=True)
    saldo_disponible = serializers.DecimalField(max_digits=9, decimal_places=1, read_only=True)
    destinos = DestinoSerializer(many=True, read_only=True)
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", default=None, read_only=True)
    aprobado_por_nombre = serializers.CharField(source="aprobado_por.nombre", default=None, read_only=True)
    propuesto_por_nombre = serializers.CharField(source="propuesto_por.nombre", default=None, read_only=True)

    class Meta:
        model = LoteLeche
        fields = [
            "id", "codigo", "fecha", "ordene", "litros", "grasa_pct", "proteina_pct", "temperatura_c",
            "observaciones", "destino", "litros_asignados", "saldo_disponible", "destinos", "estado",
            "motivo_estado", "cambios_propuestos", "propuesto_por_nombre", "creado_por_nombre",
            "fecha_creacion", "modificado_por", "fecha_modificacion", "aprobado_por_nombre",
            "fecha_aprobacion", "version",
        ]
        read_only_fields = [
            "estado", "motivo_estado", "cambios_propuestos", "fecha_creacion", "modificado_por",
            "fecha_modificacion", "fecha_aprobacion", "version",
        ]


class CrearLoteSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, help_text="Generado en el celular para no duplicar al reintentar")
    fecha = serializers.DateField()
    ordene = serializers.ChoiceField(choices=Ordene.choices)
    litros = serializers.DecimalField(max_digits=9, decimal_places=1, min_value=Decimal("0.1"))
    grasa_pct = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=15, required=False, allow_null=True)
    proteina_pct = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10, required=False, allow_null=True)
    temperatura_c = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=-5, max_value=45, required=False, allow_null=True)
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")
    destino = serializers.ChoiceField(choices=OPCIONES_DESTINO, default=DESTINO_PENDIENTE)


class EditarLoteSerializer(serializers.Serializer):
    fecha = serializers.DateField(required=False)
    ordene = serializers.ChoiceField(choices=Ordene.choices, required=False)
    litros = serializers.DecimalField(max_digits=9, decimal_places=1, min_value=Decimal("0.1"), required=False)
    grasa_pct = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=15, required=False, allow_null=True)
    proteina_pct = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10, required=False, allow_null=True)
    temperatura_c = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=-5, max_value=45, required=False, allow_null=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
    motivo = serializers.CharField(required=False, allow_blank=True, default="")


class AsignarDestinoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=TipoDestino.choices)
    litros = serializers.DecimalField(max_digits=9, decimal_places=1, min_value=Decimal("0.1"))
    nota = serializers.CharField(required=False, allow_blank=True, default="")


class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
