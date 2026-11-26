from django.contrib import admin

from .models import Auditoria, Configuracion, Establecimiento

admin.site.site_header = "ERP Tambo Kuñatai"


@admin.register(Establecimiento)
class EstablecimientoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ruc", "activo"]


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ["clave", "valor", "establecimiento"]


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ["id", "fecha", "usuario", "accion", "entidad", "entidad_id"]
    list_filter = ["accion", "entidad"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
