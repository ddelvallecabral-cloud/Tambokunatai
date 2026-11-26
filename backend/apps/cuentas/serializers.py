from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.core import auditoria

from .models import Rol, Usuario, UsuarioRol
from .servicios import modulos_de


class LoginSerializer(serializers.Serializer):
    usuario = serializers.CharField(max_length=40)
    clave = serializers.CharField(max_length=128, trim_whitespace=False)


class CambiarClaveSerializer(serializers.Serializer):
    clave_actual = serializers.CharField(trim_whitespace=False)
    clave_nueva = serializers.CharField(trim_whitespace=False, min_length=8)

    def validate(self, datos):
        usuario = self.context["request"].user
        if not usuario.check_password(datos["clave_actual"]):
            raise serializers.ValidationError({"clave_actual": "La clave actual no es correcta."})
        validate_password(datos["clave_nueva"], usuario)
        return datos


class RolSerializer(serializers.ModelSerializer):
    permisos = serializers.SlugRelatedField(slug_field="codigo", many=True, read_only=True)

    class Meta:
        model = Rol
        fields = ["id", "codigo", "nombre", "descripcion", "es_sistema", "permisos"]


class PerfilSerializer(serializers.ModelSerializer):
    """Lo que el frontend necesita para armar la sesión y el menú."""

    activo = serializers.BooleanField(source="is_active")
    roles = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()
    modulos = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ["id", "usuario", "nombre", "email", "activo", "debe_cambiar_clave", "roles", "permisos", "modulos"]

    def get_roles(self, obj):
        return [{"codigo": r.codigo, "nombre": r.nombre} for r in obj.roles.order_by("nombre")]

    def get_permisos(self, obj):
        return sorted(obj.permisos_codigos())

    def get_modulos(self, obj):
        return modulos_de(obj)


class UsuarioSerializer(serializers.ModelSerializer):
    """Alta (registro) y edición de usuarios por el Administrador."""

    activo = serializers.BooleanField(source="is_active", required=False)
    roles = serializers.SlugRelatedField(slug_field="codigo", many=True, queryset=Rol.objects.all())
    clave = serializers.CharField(write_only=True, required=False, trim_whitespace=False, min_length=8)
    ultimo_acceso = serializers.DateTimeField(source="last_login", read_only=True)

    class Meta:
        model = Usuario
        fields = [
            "id", "usuario", "nombre", "email", "telefono", "activo",
            "debe_cambiar_clave", "roles", "clave", "ultimo_acceso", "fecha_alta",
        ]
        read_only_fields = ["id", "fecha_alta"]

    def validate_usuario(self, valor):
        return valor.strip().lower()

    def validate(self, datos):
        if self.instance is None and not datos.get("clave"):
            raise serializers.ValidationError({"clave": "La clave es obligatoria al crear un usuario."})
        if datos.get("clave"):
            validate_password(datos["clave"])
        if "roles" in datos and not datos["roles"]:
            raise serializers.ValidationError({"roles": "Asigná al menos un rol."})
        return datos

    def _asignar_roles(self, usuario, roles):
        UsuarioRol.objects.filter(usuario=usuario).exclude(rol__in=roles).delete()
        for rol in roles:
            UsuarioRol.objects.get_or_create(usuario=usuario, rol=rol, establecimiento=None)
        usuario.limpiar_cache_permisos()

    @transaction.atomic
    def create(self, datos):
        roles = datos.pop("roles")
        clave = datos.pop("clave")
        usuario = Usuario.objects.create_user(password=clave, **datos)
        self._asignar_roles(usuario, roles)
        auditoria.registrar(
            "crear", "usuarios", usuario.pk,
            cambios={"usuario": usuario.usuario, "nombre": usuario.nombre, "roles": sorted(r.codigo for r in roles)},
        )
        return usuario

    @transaction.atomic
    def update(self, usuario, datos):
        roles = datos.pop("roles", None)
        clave = datos.pop("clave", None)
        cambios = {}
        for campo, valor in datos.items():
            anterior = getattr(usuario, campo)
            if anterior != valor:
                cambios[campo] = [anterior, valor]
                setattr(usuario, campo, valor)
        if clave:
            usuario.set_password(clave)
            cambios["clave"] = "restablecida"
        usuario.save()
        if cambios:
            auditoria.registrar("editar", "usuarios", usuario.pk, cambios=cambios)
        if roles is not None:
            antes = sorted(usuario.roles_codigos())
            self._asignar_roles(usuario, roles)
            despues = sorted(r.codigo for r in roles)
            if antes != despues:
                auditoria.registrar("cambio_permisos", "usuarios", usuario.pk, cambios={"roles": [antes, despues]})
        return usuario
