import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.mixins import AuditableModel


class Categoria(models.TextChoices):
    VACA = "vaca", "Vaca"
    VAQUILLONA = "vaquillona", "Vaquillona"
    TERNERA = "ternera", "Ternera"
    TORO = "toro", "Toro"
    TERNERO = "ternero", "Ternero"


class Situacion(models.TextChoices):
    EN_ORDENE = "en_ordene", "En ordeñe"
    SECA = "seca", "Seca"
    EN_RECRIA = "en_recria", "En recría"
    VENDIDA = "vendida", "Vendida"
    MUERTA = "muerta", "Muerta"


SITUACIONES_DE_BAJA = {Situacion.VENDIDA, Situacion.MUERTA}


class Animal(AuditableModel):
    """Un animal del plantel. `situacion` es su estado productivo; `estado` (del mixin) solo se usa
    para anular un alta cargada por error."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    caravana = models.CharField(max_length=20, unique=True, help_text="Número de caravana o identificación")
    nombre = models.CharField(max_length=60, blank=True)
    categoria = models.CharField(max_length=12, choices=Categoria.choices, default=Categoria.VACA)
    raza = models.CharField(max_length=40, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    situacion = models.CharField(max_length=12, choices=Situacion.choices, default=Situacion.EN_ORDENE, db_index=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "animales"
        ordering = ["caravana"]

    def __str__(self):
        return f"{self.caravana} {self.nombre}".strip()


class OrdeneVaca(models.Model):
    """Litros de una vaca en una sesión de ordeñe. La suma de una sesión es el total de su lote de leche."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    lote_leche = models.ForeignKey("leche.LoteLeche", on_delete=models.CASCADE, related_name="ordenes_vaca")
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT, related_name="ordenes")
    litros = models.DecimalField(
        max_digits=5, decimal_places=1, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(80)]
    )
    observaciones = models.CharField(max_length=255, blank=True)
    creado_por = models.ForeignKey("cuentas.Usuario", null=True, on_delete=models.PROTECT, related_name="+")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ordenes_vaca"
        ordering = ["animal__caravana"]
        constraints = [
            models.UniqueConstraint(fields=["lote_leche", "animal"], name="ordene_vaca_unico_por_sesion"),
            models.CheckConstraint(condition=Q(litros__gte=0), name="ordene_vaca_litros_no_negativos"),
        ]

    def __str__(self):
        return f"{self.animal.caravana} {self.litros} L"
