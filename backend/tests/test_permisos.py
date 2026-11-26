import pytest

from apps.core.models import Auditoria
from apps.cuentas.catalogo import CODIGOS_PERMISOS


def modulos(cliente):
    return [m["codigo"] for m in cliente.get("/api/v1/auth/me").data["modulos"]]


@pytest.mark.django_db
class TestMenuPorRol:
    def test_admin_ve_todos_los_modulos(self, como, admin):
        assert modulos(como(admin)) == [
            "inicio", "rodeo", "leche", "queso", "inventario", "compras", "ventas",
            "gastos", "aprobaciones", "reportes", "auditoria", "usuarios",
        ]

    def test_operador_ve_produccion_y_ventas_pero_no_administracion(self, como, operador):
        # Fase 4: el Operador consulta las ventas (solo lectura).
        assert modulos(como(operador)) == [
            "inicio", "rodeo", "leche", "queso", "inventario", "compras", "ventas", "gastos", "reportes",
        ]

    def test_ventas_ve_solo_lo_comercial(self, como, ventas):
        assert modulos(como(ventas)) == ["inicio", "inventario", "ventas", "gastos", "reportes"]

    def test_admin_tiene_todos_los_permisos(self, admin):
        assert admin.permisos_codigos() == CODIGOS_PERMISOS

    @pytest.mark.parametrize("permiso", ["reportes.financieros", "registros.reabrir", "auditoria.ver"])
    def test_solo_admin_tiene_finanzas_y_reapertura(self, operador, ventas, permiso):
        assert not operador.tiene_permiso(permiso)
        assert not ventas.tiene_permiso(permiso)


@pytest.mark.django_db
class TestEndpointsRestringidos:
    @pytest.mark.parametrize("url", ["/api/v1/usuarios", "/api/v1/roles", "/api/v1/auditoria"])
    def test_operador_y_ventas_reciben_403(self, como, operador, ventas, url):
        assert como(operador).get(url).status_code == 403
        assert como(ventas).get(url).status_code == 403

    @pytest.mark.parametrize("url", ["/api/v1/usuarios", "/api/v1/roles", "/api/v1/auditoria"])
    def test_admin_accede(self, como, admin, url):
        assert como(admin).get(url).status_code == 200

    def test_sin_token_es_401(self, api):
        assert api.get("/api/v1/usuarios").status_code == 401


@pytest.mark.django_db
class TestGestionDeUsuarios:
    def test_admin_registra_usuario_y_queda_auditado(self, como, admin, api):
        r = como(admin).post(
            "/api/v1/usuarios",
            {"usuario": "Juan", "nombre": "Juan Pérez", "clave": "Tambo.Juan.2026", "roles": ["OPERADOR"]},
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["usuario"] == "juan"
        assert "clave" not in r.data
        assert Auditoria.objects.filter(accion="crear", entidad="usuarios", usuario=admin).exists()
        nuevo = api.post("/api/v1/auth/login", {"usuario": "juan", "clave": "Tambo.Juan.2026"}, format="json")
        assert nuevo.status_code == 200

    def test_operador_no_puede_registrar_usuarios(self, como, operador):
        r = como(operador).post(
            "/api/v1/usuarios",
            {"usuario": "x", "nombre": "X", "clave": "Tambo.X.2026", "roles": ["ADMIN"]}, format="json",
        )
        assert r.status_code == 403

    def test_clave_debil_es_rechazada(self, como, admin):
        r = como(admin).post(
            "/api/v1/usuarios", {"usuario": "x", "nombre": "X", "clave": "12345678", "roles": ["VENTAS"]},
            format="json",
        )
        assert r.status_code == 400

    def test_cambio_de_rol_queda_auditado_y_cambia_el_menu(self, como, admin, ventas):
        r = como(admin).patch(f"/api/v1/usuarios/{ventas.pk}", {"roles": ["OPERADOR"]}, format="json")
        assert r.status_code == 200
        fila = Auditoria.objects.get(accion="cambio_permisos")
        assert fila.cambios == {"roles": [["VENTAS"], ["OPERADOR"]]}
        assert "rodeo" in modulos(como(ventas))

    def test_desactivar_usuario(self, como, admin, ventas):
        como(admin).patch(f"/api/v1/usuarios/{ventas.pk}", {"activo": False}, format="json")
        ventas.refresh_from_db()
        assert not ventas.is_active


@pytest.mark.django_db
class TestPantallaUsuarios:
    def test_alta_obliga_a_cambiar_la_clave_y_restablecer_tambien(self, como, admin, ventas):
        ad = como(admin)
        r = ad.post("/api/v1/usuarios", {"usuario": "rosa", "nombre": "Rosa", "clave": "Tambo.Rosa.2026",
                                         "roles": ["VENTAS"]}, format="json")
        assert r.status_code == 201 and r.data["debe_cambiar_clave"] is True
        r = ad.patch(f"/api/v1/usuarios/{ventas.pk}", {"clave": "Tambo.Nueva.2026"}, format="json")
        assert r.status_code == 200 and r.data["debe_cambiar_clave"] is True
        assert Auditoria.objects.filter(accion="editar", entidad_id=str(ventas.pk), cambios__clave="restablecida").exists()

    def test_el_admin_no_se_desactiva_ni_se_quita_el_rol(self, como, admin):
        ad = como(admin)
        assert ad.patch(f"/api/v1/usuarios/{admin.pk}", {"activo": False}, format="json").status_code == 400
        r = ad.patch(f"/api/v1/usuarios/{admin.pk}", {"roles": ["OPERADOR"]}, format="json")
        assert r.status_code == 400 and "a vos mismo" in str(r.data)

    def test_otro_administrador_si_puede_cambiarle_el_rol(self, como, admin):
        from .conftest import crear_usuario
        otro = crear_usuario("dueno2", "ADMIN")
        r = como(otro).patch(f"/api/v1/usuarios/{admin.pk}", {"roles": ["VENTAS"]}, format="json")
        assert r.status_code == 200
        # Ahora otro es el único Administrador: no se puede quedar sin ninguno.
        assert como(otro).patch(f"/api/v1/usuarios/{otro.pk}", {"roles": ["VENTAS"]}, format="json").status_code == 400

    def test_filtros_y_catalogo_de_permisos(self, como, admin, operador, ventas):
        ad = como(admin)
        assert [u["usuario"] for u in ad.get("/api/v1/usuarios", {"rol": "VENTAS"}).data["results"]] == ["ventas"]
        assert ad.get("/api/v1/usuarios", {"buscar": "opera"}).data["count"] == 1
        p = ad.get("/api/v1/permisos").data
        assert {"codigo": "ventas.ver", "modulo": "ventas", "descripcion": "Ver ventas y clientes"} in p
        assert como(ventas).get("/api/v1/permisos").status_code == 403
