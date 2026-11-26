import pytest
from rest_framework.test import APIClient

from apps.cuentas.catalogo import ADMIN, OPERADOR, VENTAS
from apps.cuentas.models import Rol, Usuario, UsuarioRol

CLAVE = "Clave.Segura2026"


def crear_usuario(usuario: str, rol: str, **extra) -> Usuario:
    user = Usuario.objects.create_user(usuario, CLAVE, nombre=usuario.title(), **extra)
    UsuarioRol.objects.create(usuario=user, rol=Rol.objects.get(codigo=rol))
    return user


@pytest.fixture
def admin(db):
    return crear_usuario("admin", ADMIN)


@pytest.fixture
def operador(db):
    return crear_usuario("operador", OPERADOR)


@pytest.fixture
def ventas(db):
    return crear_usuario("ventas", VENTAS)


@pytest.fixture
def api():
    return APIClient()


def login(api: APIClient, usuario: str, clave: str = CLAVE):
    return api.post("/api/v1/auth/login", {"usuario": usuario, "clave": clave}, format="json")


@pytest.fixture
def como():
    """como(usuario) -> APIClient ya autenticado con el token de ese usuario."""

    def _como(user: Usuario) -> APIClient:
        cliente = APIClient()
        respuesta = login(cliente, user.usuario)
        assert respuesta.status_code == 200, respuesta.content
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}")
        return cliente

    return _como
