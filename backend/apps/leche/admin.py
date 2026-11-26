from django.contrib import admin

from .models import DestinoLeche, LoteLeche


class DestinoInline(admin.TabularInline):
    model = DestinoLeche
    extra = 0
    readonly_fields = ["creado_por", "fecha_creacion"]


@admin.register(LoteLeche)
class LoteLecheAdmin(admin.ModelAdmin):
    list_display = ["codigo", "fecha", "ordene", "litros", "estado"]
    list_filter = ["estado", "ordene"]
    date_hierarchy = "fecha"
    inlines = [DestinoInline]
