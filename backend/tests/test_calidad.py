"""Fase 7: revisión transversal de seguridad y permisos sobre toda la API."""
import re
import uuid

import pytest
from django.urls import URLResolver, get_resolver

from .conftest import CLAVE, login

PUBLICAS = {"api/v1/salud", "api/v1/auth/login", "api/v1/auth/refresh", "api/v1/auth/logout"}


def _rutas():
    def recorrer(patrones, prefijo=""):
        for p in patrones:
            if isinstance(p, URLResolver):
                yield from recorrer(p.url_patterns, prefijo + str(p.pattern))
            else:
                yield prefijo + str(p.pattern)

    for ruta in recorrer(get_resolver().url_patterns):
        if not ruta.startswith("api/") or "format" in ruta or ruta in PUBLICAS:
            continue
        ruta = ruta.replace("^", "").replace("$", "")
        ruta = re.sub(r"\(\?P<\w+>[^)]*\)", str(uuid.uuid4()), ruta)
        ruta = re.sub(r"<int:\w+>", "1", ruta)
        ruta = re.sub(r"<(uuid:)?\w+>", str(uuid.uuid4()), ruta)
        yield "/" + ruta


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", list(_rutas()))
def test_toda_la_api_pide_sesion(api, ruta):
    for metodo in ("get", "post"):
        r = getattr(api, metodo)(ruta)
        assert r.status_code == 401, f"{metodo.upper()} {ruta} → {r.status_code}"


SOLO_ADMIN_GET = [
    "/api/v1/usuarios", "/api/v1/roles", "/api/v1/auditoria", "/api/v1/auditoria/verificar",
    "/api/v1/cuentas-por-pagar", "/api/v1/cuentas-por-pagar-resumen", "/api/v1/aprobaciones/pendientes",
    "/api/v1/reportes/estado-resultados", "/api/v1/reportes/flujo-caja", "/api/v1/reportes/rentabilidad-lotes",
    "/api/v1/reportes/rentabilidad-productos", "/api/v1/reportes/aprobaciones", "/api/v1/control/registros-editados",
    "/api/v1/reportes/estado-resultados.xlsx",
]
ID = "00000000-0000-0000-0000-000000000001"
SOLO_ADMIN_POST = [
    f"/api/v1/gastos/{ID}/aprobar", f"/api/v1/gastos/{ID}/rechazar", f"/api/v1/lotes-queso/{ID}/aprobar",
    f"/api/v1/lotes-queso/{ID}/rechazar", f"/api/v1/lotes-leche/{ID}/aprobar", f"/api/v1/lotes-leche/{ID}/reabrir",
    f"/api/v1/lotes-leche/{ID}/anular", f"/api/v1/compras/{ID}/pagar", f"/api/v1/compras/{ID}/anular",
    f"/api/v1/ventas/{ID}/anular", f"/api/v1/cuentas-por-cobrar/cobros/{ID}/anular",
    f"/api/v1/cuentas-por-pagar/pagos/{ID}/anular", "/api/v1/control/registros-editados/1/revisar", "/api/v1/usuarios",
]


@pytest.mark.parametrize("rol", ["operador", "ventas"])
def test_lo_del_administrador_queda_cerrado(rol, request, como):
    cliente = como(request.getfixturevalue(rol))
    for ruta in SOLO_ADMIN_GET:
        assert cliente.get(ruta).status_code == 403, f"{rol} GET {ruta}"
    for ruta in SOLO_ADMIN_POST:
        assert cliente.post(ruta, {}, format="json").status_code in (403, 404), f"{rol} POST {ruta}"
        # 404 solo sería aceptable si el recurso no existe; con permisos correctos debe ser 403 antes de buscarlo.
        assert cliente.post(ruta, {}, format="json").status_code == 403, f"{rol} POST {ruta}"
    assert cliente.put("/api/v1/alertas/configuracion", {}, format="json").status_code == 403


def test_bloqueo_por_usuario_tras_fallos(api, operador, settings):
    settings.LOGIN_FALLOS_MAX = 3
    for _ in range(3):
        assert login(api, "operador", "mal").status_code == 401
    r = login(api, "operador", CLAVE)
    assert r.status_code == 429 and "Demasiados intentos" in r.data["detail"]
    # Otro usuario no queda afectado.
    assert login(api, "nadie", "mal").status_code == 401


def test_un_ingreso_correcto_reinicia_el_contador(api, operador, settings):
    settings.LOGIN_FALLOS_MAX = 3
    login(api, "operador", "mal"); login(api, "operador", "mal")
    assert login(api, "operador", CLAVE).status_code == 200
    login(api, "operador", "mal"); login(api, "operador", "mal")
    assert login(api, "operador", CLAVE).status_code == 200


def test_clave_parecida_al_usuario_se_rechaza(como, operador):
    r = como(operador).post("/api/v1/auth/cambiar-clave", {"clave_actual": CLAVE, "clave_nueva": "operador2026"},
                            format="json")
    assert r.status_code == 400


def test_cabeceras_de_seguridad(api, db):
    r = api.get("/api/v1/salud")
    assert r["X-Frame-Options"] == "DENY"
    assert r["X-Content-Type-Options"] == "nosniff"


def test_errores_de_validacion_en_castellano(como, operador):
    r = como(operador).post("/api/v1/gastos", {"monto": "-5"}, format="multipart")
    assert r.status_code == 400
    assert "monto" in r.data
    mensajes = " ".join(str(m) for errores in r.data.values() for m in errores)
    assert "This field" not in mensajes and "requerido" in mensajes


def test_ip_de_auditoria_no_se_puede_falsificar(rf, settings):
    from apps.core.middleware import ip_cliente
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 2}
    # El cliente inventa "1.1.1.1"; el primer proxy propio agrega la IP real (200.1.1.1) y el segundo la suya.
    pedido = rf.get("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 200.1.1.1, 172.18.0.5")
    assert ip_cliente(pedido) == "200.1.1.1"


@pytest.mark.django_db
def test_puesta_en_marcha_crea_tambo_y_administrador(api, monkeypatch):
    from django.core.management import CommandError, call_command

    from apps.core.models import Establecimiento
    from apps.cuentas.models import Usuario

    monkeypatch.setenv("CLAVE_DUENO", "Leche.Fresca.2027")
    call_command("iniciar", establecimiento="Tambo San Juan", usuario="Juan", nombre="Juan Pérez",
                 clave_desde="CLAVE_DUENO")
    assert Establecimiento.objects.get().nombre == "Tambo San Juan"
    juan = Usuario.objects.get(usuario="juan")
    assert juan.tiene_rol("ADMIN") and juan.tiene_permiso("reportes.financieros", "gastos.gasto.aprobar")
    assert login(api, "juan", "Leche.Fresca.2027").status_code == 200
    # Solo una vez: después los usuarios se crean desde la pantalla.
    with pytest.raises(CommandError):
        call_command("iniciar", establecimiento="Otro", usuario="pedro", nombre="Pedro", clave_desde="CLAVE_DUENO")


@pytest.mark.django_db
def test_puesta_en_marcha_rechaza_clave_debil(monkeypatch):
    from django.core.management import CommandError, call_command
    monkeypatch.setenv("CLAVE_DEBIL", "12345678")
    with pytest.raises(CommandError, match="La clave no sirve"):
        call_command("iniciar", establecimiento="T", usuario="ana", nombre="Ana", clave_desde="CLAVE_DEBIL")
