from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import auditoria
from apps.core.contexto import fijar_usuario

from .models import Permiso, Rol, Usuario
from .permisos import requiere_permiso
from .serializers import (
    CambiarClaveSerializer,
    LoginSerializer,
    PerfilSerializer,
    PermisoSerializer,
    RolSerializer,
    UsuarioSerializer,
)

ERROR_LOGIN = "Usuario o clave incorrectos."
ERROR_BLOQUEO = "Demasiados intentos fallidos con este usuario. Esperá {minutos} minutos y probá de nuevo."


def _usuario_bloqueado(nombre: str) -> bool:
    """Bloqueo temporal por usuario (además del límite por IP): N fallos seguidos en la ventana.

    Se cuenta desde la auditoría, así funciona igual con varios procesos del servidor. Los fallos
    anteriores al último ingreso correcto no cuentan.
    """
    from datetime import timedelta

    from apps.core.models import Auditoria

    maximo = settings.LOGIN_FALLOS_MAX
    if not maximo:
        return False
    desde = timezone.now() - timedelta(minutes=settings.LOGIN_BLOQUEO_MINUTOS)
    ultimo_ok = Usuario.objects.filter(usuario=nombre).values_list("last_login", flat=True).first()
    if ultimo_ok and ultimo_ok > desde:
        desde = ultimo_ok
    fallos = Auditoria.objects.filter(accion="login_fallido", fecha__gte=desde, cambios__usuario=nombre).count()
    return fallos >= maximo


def _poner_cookie_refresh(response, refresh: str):
    cfg = settings.REFRESH_COOKIE
    response.set_cookie(
        cfg["key"], refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=cfg["path"], httponly=cfg["httponly"], secure=cfg["secure"], samesite=cfg["samesite"],
    )


def _borrar_cookie_refresh(response):
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(cfg["key"], path=cfg["path"], samesite=cfg["samesite"])



@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login(request):
    datos = LoginSerializer(data=request.data)
    datos.is_valid(raise_exception=True)
    nombre = datos.validated_data["usuario"].strip().lower()
    if _usuario_bloqueado(nombre):
        return Response({"detail": ERROR_BLOQUEO.format(minutos=settings.LOGIN_BLOQUEO_MINUTOS), "codigo": "bloqueado"},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    usuario = authenticate(request, usuario=nombre, password=datos.validated_data["clave"])

    if usuario is None:
        auditoria.registrar("login_fallido", "usuarios", "", usuario=None, cambios={"usuario": nombre})
        return Response({"detail": ERROR_LOGIN}, status=status.HTTP_401_UNAUTHORIZED)

    fijar_usuario(usuario)
    usuario.last_login = timezone.now()
    usuario.save(update_fields=["last_login"])
    refresh = RefreshToken.for_user(usuario)
    auditoria.registrar("login", "usuarios", usuario.pk, usuario=usuario)

    response = Response({"access": str(refresh.access_token), "usuario": PerfilSerializer(usuario).data})
    _poner_cookie_refresh(response, str(refresh))
    return response


login.cls.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([AllowAny])
def refrescar(request):
    token = request.COOKIES.get(settings.REFRESH_COOKIE["key"])
    invalido = Response({"detail": "Sesión vencida. Ingresá de nuevo."}, status=status.HTTP_401_UNAUTHORIZED)
    if not token:
        return invalido
    try:
        uid = RefreshToken(token).payload.get(settings.SIMPLE_JWT["USER_ID_CLAIM"])
        if not Usuario.objects.filter(pk=uid, is_active=True).exists():
            raise TokenError("usuario inactivo")
        serializer = TokenRefreshSerializer(data={"refresh": token})
        serializer.is_valid(raise_exception=True)
    except Exception:
        _borrar_cookie_refresh(invalido)
        return invalido

    response = Response({"access": serializer.validated_data["access"]})
    _poner_cookie_refresh(response, serializer.validated_data["refresh"])
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    token = request.COOKIES.get(settings.REFRESH_COOKIE["key"])
    if token:
        try:
            refresh = RefreshToken(token)
            uid = refresh.payload.get(settings.SIMPLE_JWT["USER_ID_CLAIM"])
            refresh.blacklist()
            usuario = Usuario.objects.filter(pk=uid).first()
            auditoria.registrar("logout", "usuarios", uid, usuario=usuario)
        except TokenError:
            pass
    response = Response(status=status.HTTP_204_NO_CONTENT)
    _borrar_cookie_refresh(response)
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def perfil(request):
    return Response(PerfilSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cambiar_clave(request):
    serializer = CambiarClaveSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    usuario = request.user
    usuario.set_password(serializer.validated_data["clave_nueva"])
    usuario.debe_cambiar_clave = False
    usuario.save(update_fields=["password", "debe_cambiar_clave"])
    auditoria.registrar("cambio_clave", "usuarios", usuario.pk)
    return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    """Usuarios. No se borran: se desactivan con `activo: false`."""

    serializer_class = UsuarioSerializer
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        qs = Usuario.objects.prefetch_related("roles").order_by("-is_active", "nombre")
        p = self.request.query_params
        if p.get("buscar"):
            t = p["buscar"].strip()
            qs = qs.filter(Q(nombre__icontains=t) | Q(usuario__icontains=t) | Q(email__icontains=t))
        if p.get("rol"):
            qs = qs.filter(roles__codigo=p["rol"])
        if p.get("activo") in ("0", "1"):
            qs = qs.filter(is_active=p["activo"] == "1")
        return qs.distinct()

    def get_permissions(self):
        codigo = "usuarios.ver" if self.action in ("list", "retrieve") else "usuarios.gestionar"
        return [requiere_permiso(codigo)()]


@api_view(["GET"])
@permission_classes([requiere_permiso("usuarios.ver")])
def permisos(request):
    """Catálogo de permisos (para la matriz de roles)."""
    return Response(PermisoSerializer(Permiso.objects.order_by("modulo", "codigo"), many=True).data)


class RolViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RolSerializer
    queryset = Rol.objects.prefetch_related("permisos")
    permission_classes = [requiere_permiso("usuarios.ver")]
    pagination_class = None
