from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Permiso, Rol, Usuario, UsuarioRol


class UsuarioRolInline(admin.TabularInline):
    model = UsuarioRol
    extra = 0


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["nombre"]
    list_display = ["usuario", "nombre", "is_active", "last_login"]
    search_fields = ["usuario", "nombre", "email"]
    list_filter = ["is_active", "roles"]
    filter_horizontal = []
    inlines = [UsuarioRolInline]
    fieldsets = [
        (None, {"fields": ["usuario", "password"]}),
        ("Datos", {"fields": ["nombre", "email", "telefono"]}),
        ("Estado", {"fields": ["is_active", "is_staff", "is_superuser", "debe_cambiar_clave", "last_login"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"], "fields": ["usuario", "nombre", "password1", "password2"]})]


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "es_sistema"]
    filter_horizontal = ["permisos"]


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "modulo", "descripcion"]
    list_filter = ["modulo"]
