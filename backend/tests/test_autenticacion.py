import pytest
from django.conf import settings

from apps.core.models import Auditoria

from .conftest import CLAVE, login

COOKIE = settings.REFRESH_COOKIE["key"]


@pytest.mark.django_db
class TestLogin:
    def test_login_correcto_devuelve_token_perfil_y_cookie(self, api, admin):
        r = login(api, "admin")
        assert r.status_code == 200
        assert r.data["access"]
        assert r.data["usuario"]["usuario"] == "admin"
        assert r.cookies[COOKIE]["httponly"]

    def test_usuario_no_distingue_mayusculas(self, api, admin):
        assert login(api, "  ADMIN ").status_code == 200

    def test_clave_incorrecta_responde_401(self, api, admin):
        r = login(api, "admin", "otra-clave")
        assert r.status_code == 401
        assert "access" not in r.data

    def test_usuario_inactivo_no_entra(self, api, admin):
        admin.is_active = False
        admin.save()
        assert login(api, "admin").status_code == 401

    def test_clave_se_guarda_hasheada(self, admin):
        assert admin.password != CLAVE
        assert admin.check_password(CLAVE)


@pytest.mark.django_db
class TestAuditoriaDeLogin:
    def test_login_exitoso_queda_auditado(self, api, operador):
        login(api, "operador")
        fila = Auditoria.objects.get(accion="login")
        assert fila.usuario == operador
        assert fila.entidad == "usuarios"
        assert fila.entidad_id == str(operador.pk)
        assert fila.rol_activo == "OPERADOR"
        assert fila.request_id is not None

    def test_login_fallido_queda_auditado_sin_usuario(self, api, operador):
        login(api, "operador", "mal")
        fila = Auditoria.objects.get(accion="login_fallido")
        assert fila.usuario is None
        assert fila.cambios == {"usuario": "operador"}

    def test_logout_queda_auditado(self, api, ventas):
        login(api, "ventas")
        api.post("/api/v1/auth/logout")
        assert Auditoria.objects.filter(accion="logout", usuario=ventas).exists()


@pytest.mark.django_db
class TestSesion:
    def test_me_sin_token_responde_401(self, api):
        assert api.get("/api/v1/auth/me").status_code == 401

    def test_me_con_token(self, como, ventas):
        r = como(ventas).get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.data["roles"] == [{"codigo": "VENTAS", "nombre": "Ventas"}]

    def test_refresh_rota_el_token_y_el_viejo_deja_de_servir(self, api, admin):
        login(api, "admin")
        viejo = api.cookies[COOKIE].value
        r = api.post("/api/v1/auth/refresh")
        assert r.status_code == 200 and r.data["access"]
        assert api.cookies[COOKIE].value != viejo
        api.cookies[COOKIE] = viejo
        assert api.post("/api/v1/auth/refresh").status_code == 401

    def test_logout_invalida_el_refresh(self, api, admin):
        login(api, "admin")
        token = api.cookies[COOKIE].value
        api.post("/api/v1/auth/logout")
        api.cookies[COOKIE] = token
        assert api.post("/api/v1/auth/refresh").status_code == 401

    def test_refresh_de_usuario_desactivado_falla(self, api, operador):
        login(api, "operador")
        operador.is_active = False
        operador.save()
        assert api.post("/api/v1/auth/refresh").status_code == 401

    def test_cambiar_clave(self, como, api, ventas):
        r = como(ventas).post(
            "/api/v1/auth/cambiar-clave",
            {"clave_actual": CLAVE, "clave_nueva": "Nueva.Clave.2026"}, format="json",
        )
        assert r.status_code == 204
        assert login(api, "ventas", "Nueva.Clave.2026").status_code == 200
        assert Auditoria.objects.filter(accion="cambio_clave").exists()
