from decimal import Decimal

from rest_framework import serializers

from apps.leche.models import Ordene
from apps.leche.serializers import OPCIONES_DESTINO

from .models import Animal


class AnimalSerializer(serializers.ModelSerializer):
    promedio_7d = serializers.SerializerMethodField()
    promedio_7d_anterior = serializers.SerializerMethodField()
    tendencia = serializers.SerializerMethodField()

    class Meta:
        model = Animal
        fields = ["id", "caravana", "nombre", "categoria", "raza", "fecha_nacimiento", "situacion",
                  "observaciones", "estado", "promedio_7d", "promedio_7d_anterior", "tendencia",
                  "fecha_creacion", "fecha_modificacion"]
        read_only_fields = ["id", "estado", "fecha_creacion", "fecha_modificacion"]

    def _prod(self, obj):
        return (self.context.get("produccion") or {}).get(obj.pk, {})

    def get_promedio_7d(self, obj):
        return self._prod(obj).get("promedio_7d")

    def get_promedio_7d_anterior(self, obj):
        return self._prod(obj).get("promedio_7d_anterior")

    def get_tendencia(self, obj):
        return self._prod(obj).get("tendencia")

    def validate_caravana(self, valor):
        return valor.strip().upper()


class ItemOrdeneSerializer(serializers.Serializer):
    animal = serializers.UUIDField()
    litros = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal("0"), max_value=Decimal("80"))
    observaciones = serializers.CharField(required=False, allow_blank=True, default="")


class RegistrarOrdeneSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    ordene = serializers.ChoiceField(choices=Ordene.choices)
    items = ItemOrdeneSerializer(many=True)
    destino = serializers.ChoiceField(choices=OPCIONES_DESTINO, default="pendiente")
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
