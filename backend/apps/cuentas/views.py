from django.conf import settings
from django.contrib.auth import authenticate
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

from .models import Rol, Usuario
from .permisos import requiere_permiso
from .serializers import (
    CambiarClaveSerializer,
    LoginSerializer,
    PerfilSerializer,
    RolSerializer,
    UsuarioSerializer,
)

ERROR_LOGIN = "Usuario o clave incorrectos."


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
    queryset = Usuario.objects.prefetch_related("roles").order_by("nombre")
    http_method_names = ["get", "post", "patch"]

    def get_permissions(self):
        codigo = "usuarios.ver" if self.action in ("list", "retrieve") else "usuarios.gestionar"
        return [requiere_permiso(codigo)()]


class RolViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RolSerializer
    queryset = Rol.objects.prefetch_related("permisos")
    permission_classes = [requiere_permiso("usuarios.ver")]
    pagination_class = None
