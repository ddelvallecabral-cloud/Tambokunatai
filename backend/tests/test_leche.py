"""Reglas de negocio del módulo de leche."""
import datetime
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.models import Auditoria
from apps.leche import servicios
from apps.leche.models import LoteLeche
from apps.leche.servicios import ReglaNegocio

HOY = datetime.date(2026, 11, 26)
AYER = HOY - datetime.timedelta(days=1)
D = Decimal


@pytest.fixture(autouse=True)
def fecha_fija(monkeypatch):
    monkeypatch.setattr(servicios, "hoy", lambda: HOY)


@pytest.fixture
def sesion():
    tokens = []

    def _sesion(usuario):
        tokens.append(iniciar_contexto(ip="10.0.0.9"))
        fijar_usuario(usuario)
        return usuario

    yield _sesion
    for t in reversed(tokens):
        terminar_contexto(t)


def lote(usuario, fecha=HOY, ordene="manana", litros="100", destino="pendiente", **extra):
    nuevo, _ = servicios.crear_lote(usuario, fecha=fecha, ordene=ordene, litros=D(litros), destino=destino, **extra)
    return LoteLeche.objects.get(pk=nuevo.pk)


@pytest.mark.django_db
class TestAltaYDestinos:
    def test_lote_nuevo_queda_pendiente_con_todo_el_saldo(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="120.5")
        assert l.destino == "pendiente"
        assert l.saldo_disponible == D("120.5")
        assert l.codigo == "LL-20261126-M"
        assert l.creado_por == operador

    def test_destino_al_cargar_asigna_todos_los_litros(self, operador, sesion):
        sesion(operador)
        l = lote(operador, destino="elaboracion_queso")
        assert l.destino == "elaboracion_queso"
        assert l.saldo_disponible == 0

    def test_repartir_entre_queso_y_venta_calcula_saldo(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="100")
        servicios.asignar_destino(operador, l, tipo="elaboracion_queso", litros=D("60"))
        servicios.asignar_destino(operador, l, tipo="venta", litros=D("25"))
        l = LoteLeche.objects.get(pk=l.pk)
        assert l.saldo_disponible == D("15")
        assert l.litros_asignados == D("85")
        assert l.destino == "mixto"

    def test_no_se_puede_asignar_mas_que_el_saldo(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="50")
        servicios.asignar_destino(operador, l, tipo="venta", litros=D("40"))
        with pytest.raises(ReglaNegocio, match="Solo quedan 10"):
            servicios.asignar_destino(operador, l, tipo="elaboracion_queso", litros=D("10.1"))

    def test_no_se_duplica_el_ordene(self, operador, sesion):
        sesion(operador)
        lote(operador)
        with pytest.raises(ReglaNegocio, match="Ya existe"):
            lote(operador)
        lote(operador, ordene="tarde")  # la otra sesión sí

    def test_reenvio_con_mismo_id_no_duplica(self, operador, sesion):
        sesion(operador)
        import uuid

        uid = uuid.uuid4()
        a, creado_a = servicios.crear_lote(operador, id=uid, fecha=HOY, ordene="manana", litros=D("80"))
        b, creado_b = servicios.crear_lote(operador, id=uid, fecha=HOY, ordene="manana", litros=D("80"))
        assert creado_a and not creado_b and a.pk == b.pk
        assert LoteLeche.objects.count() == 1

    def test_fecha_futura_rechazada(self, operador, sesion):
        sesion(operador)
        with pytest.raises(ReglaNegocio, match="futura"):
            lote(operador, fecha=HOY + datetime.timedelta(days=1))

    def test_no_se_puede_bajar_litros_por_debajo_de_lo_asignado(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="100", destino="venta")
        with pytest.raises(ReglaNegocio, match="asignados"):
            servicios.editar_lote(operador, l, {"litros": D("90")})


@pytest.mark.django_db
class TestEdicionPorFecha:
    def test_operador_edita_lote_de_hoy_directo(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="100")
        assert servicios.editar_lote(operador, l, {"litros": D("110")}) == "aplicado"
        l.refresh_from_db()
        assert l.litros == D("110") and l.estado == "borrador"
        assert Auditoria.objects.get(accion="editar").cambios == {"litros": ["100.0", "110"]}

    def test_operador_edita_lote_de_ayer_queda_pendiente_sin_cambiar_valores(self, operador, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER, litros="100")
        resultado = servicios.editar_lote(operador, l, {"litros": D("95")}, "Se midió mal el tarro")
        assert resultado == "pendiente"
        l.refresh_from_db()
        assert l.estado == "pendiente"
        assert l.litros == D("100")  # el valor no cambia hasta que se apruebe
        assert l.cambios_propuestos == {"litros": "95", "_motivo": "Se midió mal el tarro"}
        assert l.propuesto_por == operador
        assert Auditoria.objects.filter(accion="proponer_correccion").exists()

    def test_no_se_propone_dos_veces(self, operador, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER)
        servicios.editar_lote(operador, l, {"litros": D("95")})
        with pytest.raises(ReglaNegocio, match="esperando aprobación"):
            servicios.editar_lote(operador, l, {"litros": D("96")})

    def test_admin_aprueba_y_se_aplica(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER, litros="100")
        servicios.editar_lote(operador, l, {"litros": D("95"), "grasa_pct": D("3.6")})
        sesion(admin)
        servicios.aprobar_correccion(admin, l)
        l.refresh_from_db()
        assert (l.litros, l.grasa_pct, l.estado) == (D("95"), D("3.6"), "aprobado")
        assert l.aprobado_por == admin and l.cambios_propuestos is None
        assert Auditoria.objects.get(accion="aplicar_correccion").usuario == admin

    def test_admin_rechaza_y_se_descarta(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER, litros="100")
        servicios.editar_lote(operador, l, {"litros": D("95")})
        sesion(admin)
        servicios.rechazar_correccion(admin, l, "El tarro estaba bien medido")
        l.refresh_from_db()
        assert (l.litros, l.estado, l.cambios_propuestos) == (D("100"), "rechazado", None)
        # el operador puede volver a proponer
        sesion(operador)
        assert servicios.editar_lote(operador, l, {"litros": D("97")}) == "pendiente"

    def test_rechazo_exige_motivo(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER)
        servicios.editar_lote(operador, l, {"litros": D("95")})
        sesion(admin)
        with pytest.raises(Exception, match="motivo"):
            servicios.rechazar_correccion(admin, l, "")

    def test_admin_edita_lote_de_ayer_directo(self, admin, sesion):
        sesion(admin)
        l = lote(admin, fecha=AYER, litros="100")
        assert servicios.editar_lote(admin, l, {"litros": D("101")}) == "aplicado"


@pytest.mark.django_db
class TestLotesCerrados:
    def test_cerrar_exige_saldo_cero(self, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="100")
        servicios.asignar_destino(operador, l, tipo="venta", litros=D("70"))
        with pytest.raises(ReglaNegocio, match="30.0 L sin destino"):
            servicios.cerrar_lote(operador, l)
        servicios.asignar_destino(operador, l, tipo="descarte", litros=D("30"))
        servicios.cerrar_lote(operador, l)
        assert LoteLeche.objects.get(pk=l.pk).estado == "cerrado"

    def test_operador_no_edita_cerrado(self, operador, sesion):
        sesion(operador)
        l = lote(operador, destino="venta")
        servicios.cerrar_lote(operador, l)
        with pytest.raises(ReglaNegocio, match="solo el Administrador"):
            servicios.editar_lote(operador, l, {"observaciones": "x"})

    def test_admin_edita_cerrado_con_motivo_y_queda_auditado(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, destino="venta")
        servicios.cerrar_lote(operador, l)
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="motivo"):
            servicios.editar_lote(admin, l, {"temperatura_c": D("4.5")})
        servicios.editar_lote(admin, l, {"temperatura_c": D("4.5")}, "Faltaba la temperatura")
        l.refresh_from_db()
        assert l.temperatura_c == D("4.5") and l.estado == "cerrado"
        fila = Auditoria.objects.get(accion="editar_bloqueado")
        assert fila.motivo == "Faltaba la temperatura" and fila.usuario == admin

    def test_no_se_asignan_destinos_a_un_lote_cerrado(self, operador, sesion):
        sesion(operador)
        l = lote(operador, destino="venta")
        servicios.cerrar_lote(operador, l)
        with pytest.raises(ReglaNegocio, match="cerrado"):
            servicios.asignar_destino(operador, l, tipo="venta", litros=D("1"))

    def test_operador_no_quita_destinos_de_dias_anteriores(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER, destino="venta")
        destino = l.destinos.get()
        with pytest.raises(ReglaNegocio, match="Administrador"):
            servicios.quitar_destino(operador, destino)
        sesion(admin)
        servicios.quitar_destino(admin, destino, "Era para queso")
        assert LoteLeche.objects.get(pk=l.pk).saldo_disponible == D("100")


@pytest.mark.django_db
class TestResumenYTablero:
    def _cargar(self, usuario):
        a = lote(usuario, HOY, "manana", "120")
        servicios.asignar_destino(usuario, a, tipo="elaboracion_queso", litros=D("100"))
        servicios.asignar_destino(usuario, a, tipo="venta", litros=D("15"))
        lote(usuario, HOY, "tarde", "80", destino="venta")
        lote(usuario, AYER, "manana", "110")
        lote(usuario, AYER, "tarde", "90", destino="descarte")

    def test_resumen_diario_por_ordene_y_destino(self, operador, sesion):
        sesion(operador)
        self._cargar(operador)
        r = servicios.resumen_dia(HOY)
        assert r["total_litros"] == D("200")
        assert r["por_ordene"] == {"manana": D("120"), "tarde": D("80")}
        assert r["por_destino"] == {
            "venta": D("95"), "elaboracion_queso": D("100"), "descarte": D("0"), "pendiente": D("5"),
        }
        assert r["ordenes_faltantes"] == []

    def test_resumen_excluye_anulados(self, operador, admin, sesion):
        sesion(operador)
        l = lote(operador, litros="50")
        sesion(admin)
        l.anular("Cargado dos veces")
        assert servicios.resumen_dia(HOY)["total_litros"] == 0

    def test_tablero_suma_dia_y_mes(self, operador, sesion):
        sesion(operador)
        self._cargar(operador)
        lote(operador, datetime.date(2026, 10, 31), "manana", "999")  # otro mes, no cuenta
        t = servicios.tablero()
        assert t["hoy"]["total_litros"] == D("200")
        assert t["mes"]["litros"] == D("400")
        assert t["mes"]["dias_con_carga"] == 2
        assert t["mes"]["promedio_diario"] == D("200.0")
        assert len(t["ultimos_14_dias"]) == 14
        assert t["ultimos_14_dias"][-1] == {"fecha": HOY, "litros": D("200")}

    @override_settings(LECHE_UMBRAL_LITROS_DIARIOS=250)
    def test_alerta_si_el_dia_completo_queda_bajo_el_umbral(self, operador, sesion):
        sesion(operador)
        self._cargar(operador)
        mensajes = [a["mensaje"] for a in servicios.tablero()["alertas"]]
        assert any(m.startswith("Hoy se ordeñaron 200") for m in mensajes)
        assert any(m.startswith("Ayer se ordeñaron 200") for m in mensajes)

    @override_settings(LECHE_UMBRAL_LITROS_DIARIOS=150)
    def test_no_alerta_hoy_si_falta_un_ordene(self, operador, sesion):
        sesion(operador)
        lote(operador, HOY, "manana", "100")  # falta la tarde: todavía no es poco
        lote(operador, AYER, "manana", "100")
        lote(operador, AYER, "tarde", "100")
        assert servicios.tablero()["alertas"] == []

    @override_settings(LECHE_UMBRAL_LITROS_DIARIOS=None)
    def test_sin_umbral_no_hay_alertas(self, operador, sesion):
        sesion(operador)
        lote(operador, HOY, "manana", "1")
        assert servicios.tablero()["alertas"] == []

    def test_tablero_cuenta_correcciones_pendientes(self, operador, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER)
        servicios.editar_lote(operador, l, {"litros": D("1")})
        assert servicios.tablero()["correcciones_pendientes"] == 1


@pytest.mark.django_db
class TestApiLeche:
    def test_operador_carga_desde_el_celular(self, como, operador):
        r = como(operador).post(
            "/api/v1/lotes-leche",
            {"fecha": str(HOY), "ordene": "manana", "litros": "132.5", "destino": "elaboracion_queso"},
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["codigo"] == "LL-20261126-M"
        assert r.data["saldo_disponible"] == "0.0"

    def test_ventas_no_accede(self, como, ventas):
        assert como(ventas).get("/api/v1/lotes-leche").status_code == 403
        assert como(ventas).get("/api/v1/leche/tablero").status_code == 403

    def test_operador_no_puede_aprobar(self, como, operador, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER)
        servicios.editar_lote(operador, l, {"litros": D("1")})
        assert como(operador).post(f"/api/v1/lotes-leche/{l.pk}/aprobar").status_code == 403

    def test_edicion_de_ayer_por_api_responde_pendiente(self, como, operador, sesion):
        sesion(operador)
        l = lote(operador, fecha=AYER, litros="100")
        r = como(operador).patch(f"/api/v1/lotes-leche/{l.pk}", {"litros": "90", "motivo": "error"}, format="json")
        assert r.status_code == 200
        assert r.data["resultado"] == "pendiente" and r.data["estado"] == "pendiente"
        assert r.data["litros"] == "100.0"

    def test_asignar_de_mas_responde_409(self, como, operador, sesion):
        sesion(operador)
        l = lote(operador, litros="10")
        r = como(operador).post(f"/api/v1/lotes-leche/{l.pk}/destinos", {"tipo": "venta", "litros": "11"}, format="json")
        assert r.status_code == 409 and "Solo quedan" in r.data["detail"]

    def test_filtros_del_listado(self, como, operador, sesion):
        sesion(operador)
        TestResumenYTablero()._cargar(operador)
        c = como(operador)
        assert len(c.get("/api/v1/lotes-leche", {"fecha": str(HOY)}).data["results"]) == 2
        assert len(c.get("/api/v1/lotes-leche", {"destino": "pendiente"}).data["results"]) == 2
        assert len(c.get("/api/v1/lotes-leche", {"destino": "descarte"}).data["results"]) == 1
        assert len(c.get("/api/v1/lotes-leche", {"desde": str(AYER), "hasta": str(AYER)}).data["results"]) == 2

    def test_menu_del_operador_tiene_leche_habilitado(self, como, operador):
        modulos = {m["codigo"]: m for m in como(operador).get("/api/v1/auth/me").data["modulos"]}
        assert modulos["leche"]["disponible"] is True
