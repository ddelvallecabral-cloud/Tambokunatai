"""Mixin de auditoría para las entidades del ERP.

Uso en fases siguientes:

    class LoteQueso(AuditableModel):
        ...

Con solo heredar, la entidad obtiene:
- creado_por / fecha_creacion / modificado_por / fecha_modificacion, completados solos
  con el usuario autenticado de la petición.
- estado (borrador → pendiente → aprobado → cerrado, más rechazado y anulado),
  aprobado_por / fecha_aprobacion, y `version` para bloqueo optimista.
- Una fila en `auditoria` por cada alta, edición (solo campos cambiados) y transición.
- Bloqueo: un registro aprobado, cerrado o anulado no se puede editar; solo reabrir()
  (que el Administrador ejecuta con motivo) lo vuelve a borrador.
"""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from . import auditoria
from .contexto import usuario_actual


class EstadoRegistro(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    PENDIENTE = "pendiente", "Pendiente de aprobación"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    CERRADO = "cerrado", "Cerrado"
    ANULADO = "anulado", "Anulado"


ESTADOS_BLOQUEADOS = {EstadoRegistro.APROBADO, EstadoRegistro.CERRADO, EstadoRegistro.ANULADO}

# Desde qué estados se puede llegar a cada uno.
TRANSICIONES = {
    "enviar": ({EstadoRegistro.BORRADOR, EstadoRegistro.RECHAZADO}, EstadoRegistro.PENDIENTE),
    "aprobar": ({EstadoRegistro.PENDIENTE}, EstadoRegistro.APROBADO),
    "rechazar": ({EstadoRegistro.PENDIENTE}, EstadoRegistro.RECHAZADO),
    # Cerrar desde borrador sirve a entidades sin aprobación previa (p. ej. lotes de leche);
    # las entidades que exigen aprobación lo controlan en su servicio.
    "cerrar": ({EstadoRegistro.BORRADOR, EstadoRegistro.APROBADO}, EstadoRegistro.CERRADO),
    "reabrir": ({EstadoRegistro.APROBADO, EstadoRegistro.CERRADO, EstadoRegistro.RECHAZADO}, EstadoRegistro.BORRADOR),
    "anular": (
        {EstadoRegistro.BORRADOR, EstadoRegistro.PENDIENTE, EstadoRegistro.APROBADO,
         EstadoRegistro.RECHAZADO, EstadoRegistro.CERRADO},
        EstadoRegistro.ANULADO,
    ),
}

# Campos que maneja el mixin y no se listan como "cambios" de una edición.
CAMPOS_CONTROL = {"fecha_creacion", "fecha_modificacion", "modificado_por_id", "version"}


# Ediciones especiales que el servicio autoriza explícitamente (p. ej. el Administrador
# corrigiendo un registro cerrado). Se auditan con su propio nombre y motivo.
ACCIONES_DE_EDICION = {"editar_bloqueado", "aplicar_correccion"}


class RegistroBloqueado(Exception):
    pass


class TransicionInvalida(Exception):
    pass


class AuditableModel(models.Model):
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    fecha_modificacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=20, choices=EstadoRegistro.choices, default=EstadoRegistro.BORRADOR, db_index=True)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, editable=False)
    motivo_estado = models.TextField(blank=True, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        abstract = True

    # --- utilidades -------------------------------------------------------
    @classmethod
    def nombre_entidad(cls) -> str:
        return cls._meta.db_table

    def _valores(self) -> dict:
        return {f.attname: getattr(self, f.attname) for f in self._meta.concrete_fields}

    @property
    def esta_bloqueado(self) -> bool:
        return self.estado in ESTADOS_BLOQUEADOS

    # --- guardado ---------------------------------------------------------
    def save(self, *args, **kwargs):
        accion = getattr(self, "_accion_en_curso", None)
        usuario = usuario_actual()
        es_alta = self._state.adding

        with transaction.atomic():
            anterior = None
            if not es_alta:
                anterior = type(self).objects.select_for_update().filter(pk=self.pk).first()
                if anterior is None:
                    es_alta = True
            if es_alta:
                if self.creado_por_id is None and usuario is not None:
                    self.creado_por = usuario
            else:
                if anterior.estado in ESTADOS_BLOQUEADOS and accion is None:
                    raise RegistroBloqueado(
                        f"El registro está {anterior.get_estado_display().lower()} y no se puede editar. "
                        "Solo el Administrador puede reabrirlo."
                    )
                if usuario is not None:
                    self.modificado_por = usuario
                self.version = anterior.version + 1

            super().save(*args, **kwargs)

            if es_alta:
                auditoria.registrar("crear", self.nombre_entidad(), self.pk, cambios=self._valores())
            elif accion is None or accion in ACCIONES_DE_EDICION:
                antes, despues = anterior._valores(), self._valores()
                cambios = {
                    k: [antes[k], despues[k]]
                    for k in despues
                    if k not in CAMPOS_CONTROL and antes.get(k) != despues[k]
                }
                if cambios:
                    auditoria.registrar(
                        accion or "editar", self.nombre_entidad(), self.pk,
                        cambios=cambios, motivo=getattr(self, "_motivo_en_curso", "") or "",
                    )

    # --- transiciones de estado ------------------------------------------
    def _transicion(self, accion: str, motivo: str = "", snapshot: bool = False):
        origenes, destino = TRANSICIONES[accion]
        if self.estado not in origenes:
            raise TransicionInvalida(f"No se puede {accion} un registro en estado {self.estado}.")
        if accion in {"rechazar", "reabrir", "anular"} and not motivo.strip():
            raise TransicionInvalida(f"Para {accion} hace falta indicar el motivo.")
        estado_anterior = self.estado
        self.estado = destino
        self.motivo_estado = motivo
        if accion == "aprobar":
            self.aprobado_por = usuario_actual()
            self.fecha_aprobacion = timezone.now()
        if accion == "reabrir":
            self.aprobado_por = None
            self.fecha_aprobacion = None
        self._accion_en_curso = accion
        try:
            with transaction.atomic():
                self.save()
                auditoria.registrar(
                    accion,
                    self.nombre_entidad(),
                    self.pk,
                    cambios={"estado": [estado_anterior, destino]},
                    snapshot=self._valores() if snapshot else None,
                    motivo=motivo,
                )
        finally:
            self._accion_en_curso = None
        return self

    def guardar_edicion_autorizada(self, accion: str, motivo: str = ""):
        """Guarda cambios saltando el bloqueo por estado. Solo la llama un servicio que ya verificó
        el permiso (p. ej. Administrador editando un registro cerrado). Queda auditado con motivo."""
        assert accion in ACCIONES_DE_EDICION, accion
        self._accion_en_curso, self._motivo_en_curso = accion, motivo
        try:
            self.save()
        finally:
            self._accion_en_curso, self._motivo_en_curso = None, ""

    def enviar(self):
        return self._transicion("enviar")

    def aprobar(self):
        return self._transicion("aprobar", snapshot=True)

    def rechazar(self, motivo: str):
        return self._transicion("rechazar", motivo)

    def cerrar(self):
        return self._transicion("cerrar", snapshot=True)

    def reabrir(self, motivo: str):
        return self._transicion("reabrir", motivo)

    def anular(self, motivo: str):
        return self._transicion("anular", motivo, snapshot=True)
