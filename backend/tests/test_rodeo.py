"""Fase 3: rodeo y ordeñe por vaca y por sesión."""
import datetime
from decimal import Decimal

import pytest

from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.mixins import ReglaNegocio
from apps.core.models import Auditoria
from apps.leche import servicios as leche
from apps.leche.models import LoteLeche
from apps.rodeo import servicios as rodeo
from apps.rodeo.models import Animal, OrdeneVaca

HOY = datetime.date(2026, 11, 26)
AYER = HOY - datetime.timedelta(days=1)
D = Decimal


@pytest.fixture(autouse=True)
def fecha_fija(monkeypatch):
    monkeypatch.setattr(leche, "hoy", lambda: HOY)


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


@pytest.fixture
def vacas(db, operador, sesion):
    sesion(operador)
    return [Animal.objects.create(caravana=c, nombre=n) for c, n in (("101", "Pintada"), ("102", "Mora"), ("103", "Negra"))]


def planilla(usuario, litros, fecha=HOY, ordene="manana", **extra):
    return rodeo.registrar_ordene(
        usuario, fecha=fecha, ordene=ordene,
        items=[{"animal": a, "litros": D(x)} for a, x in litros], **extra)


@pytest.mark.django_db
class TestOrdenePorVaca:
    def test_la_planilla_crea_el_lote_con_la_suma_de_las_vacas(self, operador, vacas):
        r = planilla(operador, [(vacas[0], "14.5"), (vacas[1], "12"), (vacas[2], "0")])
        assert r["creado"] and r["total"] == D("26.5")
        lote = r["lote"]
        assert lote.litros == D("26.5") and lote.codigo == "LL-20261126-M"
        assert OrdeneVaca.objects.filter(lote_leche=lote).count() == 3
        assert Auditoria.objects.filter(accion="ordene_por_vaca", entidad_id=str(lote.pk)).count() == 1

    def test_reenviar_la_misma_planilla_no_cambia_nada(self, operador, vacas):
        planilla(operador, [(vacas[0], "14.5"), (vacas[1], "12")])
        auditorias = Auditoria.objects.count()
        r = planilla(operador, [(vacas[0], "14.5"), (vacas[1], "12")])
        assert not r["creado"] and r["vacas_cambiadas"] == 0
        assert LoteLeche.objects.count() == 1 and OrdeneVaca.objects.count() == 2
        assert Auditoria.objects.count() == auditorias

    def test_corregir_el_mismo_dia_actualiza_el_total_del_lote(self, operador, vacas):
        planilla(operador, [(vacas[0], "14.5"), (vacas[1], "12")])
        r = planilla(operador, [(vacas[0], "15"), (vacas[2], "9")])  # la 102 se sacó, la 103 se agregó
        assert r["total_anterior"] == D("26.5") and r["total"] == D("24")
        assert LoteLeche.objects.get().litros == D("24")
        assert set(OrdeneVaca.objects.values_list("animal__caravana", flat=True)) == {"101", "103"}
        cambios = Auditoria.objects.filter(accion="ordene_por_vaca").order_by("-id").first().cambios
        assert cambios == {"101": ["14.5", "15"], "103": [None, "9"], "102": ["12.0", None]}

    def test_reemplaza_un_lote_cargado_como_total(self, operador, vacas):
        leche.crear_lote(operador, fecha=HOY, ordene="manana", litros=D("30"))
        r = planilla(operador, [(vacas[0], "14"), (vacas[1], "13")])
        assert not r["creado"] and r["total_anterior"] == D("30.0")
        assert LoteLeche.objects.get().litros == D("27")

    def test_no_baja_el_total_por_debajo_de_lo_ya_destinado(self, operador, vacas):
        r = planilla(operador, [(vacas[0], "14"), (vacas[1], "13")], destino="venta")
        assert r["lote"].saldo_disponible == 0
        with pytest.raises(ReglaNegocio, match="asignados"):
            planilla(operador, [(vacas[0], "14")])
        assert OrdeneVaca.objects.count() == 2  # no quedó nada a medias

    def test_operador_no_corrige_dias_anteriores_el_admin_si(self, admin, operador, sesion, vacas):
        planilla(operador, [(vacas[0], "14")], fecha=AYER)
        with pytest.raises(ReglaNegocio, match="Administrador"):
            planilla(operador, [(vacas[0], "15")], fecha=AYER)
        sesion(admin)
        planilla(admin, [(vacas[0], "15")], fecha=AYER)
        assert LoteLeche.objects.get().litros == D("15")

    def test_lote_cerrado_solo_admin_con_motivo(self, admin, operador, sesion, vacas):
        r = planilla(operador, [(vacas[0], "14")], destino="venta")
        leche.cerrar_lote(operador, r["lote"])
        with pytest.raises(ReglaNegocio, match="cerrado"):
            planilla(operador, [(vacas[0], "14"), (vacas[1], "1")])
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="motivo"):
            planilla(admin, [(vacas[0], "14"), (vacas[1], "0")])
        planilla(admin, [(vacas[0], "14"), (vacas[1], "0")], motivo="Faltó anotar la 102")
        assert OrdeneVaca.objects.count() == 2

    def test_vaca_dada_de_baja_o_repetida_es_rechazada(self, operador, vacas):
        vacas[2].situacion = "vendida"
        vacas[2].save()
        with pytest.raises(ReglaNegocio, match="dada de baja"):
            planilla(operador, [(vacas[2], "10")])
        with pytest.raises(ReglaNegocio, match="repetida"):
            planilla(operador, [(vacas[0], "10"), (vacas[0], "11")])
        with pytest.raises(ReglaNegocio, match="futura"):
            planilla(operador, [(vacas[0], "10")], fecha=HOY + datetime.timedelta(days=1))

    def test_planilla_lista_las_vacas_en_ordene_con_lo_cargado(self, operador, vacas):
        vacas[2].situacion = "seca"
        vacas[2].save()
        planilla(operador, [(vacas[0], "14")])
        p = rodeo.planilla(HOY, "manana")
        assert [(f["caravana"], f["litros"]) for f in p["vacas"]] == [("101", D("14.0")), ("102", None)]
        assert p["lote"]["con_detalle_por_vaca"] is True


@pytest.mark.django_db
class TestTendencia:
    def test_compara_la_ultima_semana_con_la_anterior(self, operador, vacas):
        for dias in range(14):
            fecha = HOY - datetime.timedelta(days=dias)
            reciente = dias < 7
            planilla(operador, [
                (vacas[0], "12" if reciente else "10"),   # sube 20 %
                (vacas[1], "8" if reciente else "10"),    # baja 20 %
                (vacas[2], "10"),                         # estable
            ], fecha=fecha)
        prod = rodeo.produccion_por_animal(HOY)
        assert prod[vacas[0].pk] == {"promedio_7d": D("12.0"), "promedio_7d_anterior": D("10.0"), "tendencia": "sube"}
        assert prod[vacas[1].pk]["tendencia"] == "baja"
        assert prod[vacas[2].pk]["tendencia"] == "estable"
        serie = rodeo.serie_animal(vacas[0], dias=7, fecha=HOY)
        assert len(serie) == 7 and serie[-1]["total"] == D("12.0")

    def test_suma_mañana_y_tarde_del_mismo_dia(self, operador, vacas):
        planilla(operador, [(vacas[0], "12")], fecha=AYER, ordene="manana")
        planilla(operador, [(vacas[0], "9")], fecha=AYER, ordene="tarde")
        assert rodeo.produccion_por_animal(HOY)[vacas[0].pk]["promedio_7d"] == D("21.0")

    def test_sin_semana_anterior_no_hay_tendencia(self, operador, vacas):
        planilla(operador, [(vacas[0], "12")])
        assert rodeo.produccion_por_animal(HOY)[vacas[0].pk]["tendencia"] is None


@pytest.mark.django_db
class TestApiRodeo:
    def test_alta_de_vaca_y_planilla_por_api(self, como, operador):
        op = como(operador)
        r = op.post("/api/v1/animales", {"caravana": " 201a ", "nombre": "Colorada"}, format="json")
        assert r.status_code == 201 and r.data["caravana"] == "201A"
        assert op.post("/api/v1/animales", {"caravana": "201A"}, format="json").status_code == 400
        p = op.get("/api/v1/rodeo/ordene", {"fecha": str(HOY), "ordene": "tarde"}).data
        assert p["lote"] is None and p["vacas"][0]["caravana"] == "201A"
        r = op.post("/api/v1/rodeo/ordene", {"fecha": str(HOY), "ordene": "tarde",
                                             "items": [{"animal": r.data["id"], "litros": "0"}]}, format="json")
        assert r.status_code == 409 and "mayor a cero" in r.data["detail"]

    def test_ventas_no_entra_al_rodeo(self, como, ventas):
        assert como(ventas).get("/api/v1/rodeo/ordene").status_code == 403
