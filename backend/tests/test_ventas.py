"""Fase 4: clientes, precios, ventas, cuentas por cobrar y trazabilidad hasta el cliente."""
import datetime
import uuid
from decimal import Decimal

import pytest

from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.mixins import ReglaNegocio
from apps.core.models import Auditoria
from apps.inventario.models import MovimientoInventario
from apps.leche import servicios as leche
from apps.leche.models import LoteLeche
from apps.queso import servicios as queso
from apps.queso.models import LoteQueso
from apps.ventas import servicios as ventas_srv
from apps.ventas.models import Cliente, CuentaPorCobrar, Precio, Venta

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
def precios(admin, sesion):
    sesion(admin)
    Precio.objects.create(producto="queso", precio_unitario=40_000)
    Precio.objects.create(producto="queso", tipo_cliente="mayorista", precio_unitario=36_000)
    Precio.objects.create(producto="queso", cantidad_minima=D("20"), precio_unitario=35_000)
    Precio.objects.create(producto="leche", precio_unitario=3_500)


@pytest.fixture
def clientes(admin, sesion, precios):
    sesion(admin)
    return {
        "almacen": Cliente.objects.create(nombre="Almacén Doña Rosa", tipo="minorista"),
        "super": Cliente.objects.create(nombre="Super Central", tipo="mayorista", condicion_pago="credito_15"),
    }


def lote_queso_aprobado(operador, admin, sesion, kg, fecha=HOY, litros="100"):
    """Un lote elaborado por el Operador y aprobado por el Administrador."""
    sesion(operador)
    ll, _ = leche.crear_lote(operador, fecha=fecha, ordene="manana" if not LoteLeche.objects.filter(
        fecha=fecha, ordene="manana").exists() else "tarde", litros=D(litros))
    lq, _ = queso.iniciar_lote(operador, fecha=fecha, origenes=[{"lote_leche": ll, "litros": D(litros)}], insumos=[])
    lq = queso.cerrar_lote(operador, LoteQueso.objects.get(pk=lq.pk), kg_obtenidos=D(kg))
    sesion(admin)
    return queso.aprobar_lote(admin, lq, "OK")


@pytest.fixture
def quesos(operador, admin, sesion):
    """Dos lotes aprobados: 11 kg de ayer (más viejo) y 10 kg de hoy."""
    viejo = lote_queso_aprobado(operador, admin, sesion, "11", fecha=AYER)
    nuevo = lote_queso_aprobado(operador, admin, sesion, "10", fecha=HOY)
    return viejo, nuevo


def vender(usuario, cliente, cantidad, producto="queso", **extra):
    venta, _ = ventas_srv.registrar_venta(usuario, cliente=cliente, producto=producto, cantidad=D(cantidad), **extra)
    return venta


def stock_queso_kg():
    return queso.resumen_inventario_queso()["kg_disponibles"]


# --- Precios ---------------------------------------------------------------------------------

@pytest.mark.django_db
class TestPrecios:
    def test_precio_por_tipo_de_cliente_y_por_volumen(self, precios):
        assert ventas_srv.precio_para("minorista", "queso", D("5"))[0] == 40_000
        assert ventas_srv.precio_para("mayorista", "queso", D("5"))[0] == 36_000
        assert ventas_srv.precio_para("minorista", "queso", D("20"))[0] == 35_000  # por volumen
        assert ventas_srv.precio_para("minorista", "leche", D("50"))[0] == 3_500

    def test_sin_precio_cargado_no_se_vende(self, db):
        with pytest.raises(ReglaNegocio, match="No hay precio"):
            ventas_srv.precio_para("minorista", "queso", D("1"))

    def test_ventas_no_cambia_precios_ni_vende_fuera_de_lista(self, como, ventas, admin, sesion, clientes, quesos):
        op = como(ventas)
        assert op.get("/api/v1/precios").status_code == 200
        assert op.post("/api/v1/precios", {"producto": "queso", "precio_unitario": 1}, format="json").status_code == 403
        precio = Precio.objects.filter(producto="leche").first()
        assert op.patch(f"/api/v1/precios/{precio.pk}", {"precio_unitario": 1}, format="json").status_code == 403
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="Solo el Administrador puede cambiar el precio"):
            vender(ventas, clientes["almacen"], "1", precio_unitario=30_000)
        sesion(admin)
        v = vender(admin, clientes["almacen"], "1", precio_unitario=30_000)
        assert v.precio_unitario == 30_000 and v.precio_de_lista == 40_000 and v.total == 30_000

    def test_admin_cambia_la_tabla_de_precios(self, como, admin, precios):
        ad = como(admin)
        r = ad.post("/api/v1/precios", {"producto": "queso", "tipo_cliente": "mayorista", "precio_unitario": 1}, format="json")
        assert r.status_code == 400 and "Ya hay un precio activo" in str(r.data)
        fila = Precio.objects.get(producto="queso", tipo_cliente="mayorista")
        assert ad.patch(f"/api/v1/precios/{fila.pk}", {"precio_unitario": 37_000}, format="json").status_code == 200
        assert ventas_srv.precio_para("mayorista", "queso", D("1"))[0] == 37_000
        assert ad.post("/api/v1/precios", {"producto": "leche", "cantidad_minima": "100", "precio_unitario": 3_200},
                       format="json").status_code == 201
        assert ventas_srv.precio_para("minorista", "leche", D("150"))[0] == 3_200


# --- Registrar venta -------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegistrarVenta:
    def test_descuenta_el_inventario_y_genera_la_cuenta(self, ventas, sesion, clientes, quesos):
        viejo, nuevo = quesos
        assert stock_queso_kg() == D("21")
        sesion(ventas)
        v = vender(ventas, clientes["super"], "13.5")
        assert v.codigo == "V-00001" and v.precio_unitario == 36_000 and v.total == 486_000
        assert v.estado_venta == "pendiente"
        # Sale primero el lote más viejo, completo, y el resto del nuevo.
        assert sorted((l.lote_queso.codigo, l.cantidad) for l in v.lotes.all()) == [
            (viejo.codigo, D("11")), (nuevo.codigo, D("2.5"))]
        assert stock_queso_kg() == D("7.5")
        assert MovimientoInventario.objects.filter(venta=v, tipo="salida", motivo="venta").count() == 2
        cuenta = CuentaPorCobrar.objects.get(venta=v)
        assert cuenta.monto == 486_000 and cuenta.saldo == 486_000 and cuenta.estado == "pendiente"
        assert cuenta.vencimiento == HOY + datetime.timedelta(days=15)  # crédito 15 días del cliente
        assert Auditoria.objects.filter(accion="registrar_venta", entidad_id=str(v.pk)).exists()

    def test_no_se_vende_mas_que_el_inventario_y_no_queda_nada_a_medias(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="No hay stock suficiente: hay 21 kg"):
            vender(ventas, clientes["almacen"], "21.5")
        assert Venta.objects.count() == 0 and CuentaPorCobrar.objects.count() == 0
        assert stock_queso_kg() == D("21")
        vender(ventas, clientes["almacen"], "21")
        with pytest.raises(ReglaNegocio, match="No hay stock suficiente"):
            vender(ventas, clientes["almacen"], "0.1")

    def test_queso_sin_aprobar_no_se_vende(self, operador, ventas, sesion, clientes):
        sesion(operador)
        ll, _ = leche.crear_lote(operador, fecha=HOY, ordene="manana", litros=D("100"))
        lq, _ = queso.iniciar_lote(operador, fecha=HOY, origenes=[{"lote_leche": ll, "litros": D("100")}], insumos=[])
        queso.cerrar_lote(operador, LoteQueso.objects.get(pk=lq.pk), kg_obtenidos=D("11"))
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="hay 0 kg"):
            vender(ventas, clientes["almacen"], "1")

    def test_lote_elegido_a_mano(self, ventas, sesion, clientes, quesos):
        viejo, nuevo = quesos
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "3", lotes=[{"lote": nuevo.pk, "cantidad": D("3")}])
        assert [l.lote_queso_id for l in v.lotes.all()] == [nuevo.pk]
        with pytest.raises(ReglaNegocio, match="tiene 7 kg"):
            vender(ventas, clientes["almacen"], "8", lotes=[{"lote": nuevo.pk, "cantidad": D("8")}])
        with pytest.raises(ReglaNegocio, match="no suma"):
            vender(ventas, clientes["almacen"], "5", lotes=[{"lote": nuevo.pk, "cantidad": D("3")}])

    def test_venta_de_leche_usa_el_saldo_y_bloquea_el_lote(self, operador, admin, ventas, sesion, clientes):
        sesion(operador)
        ll, _ = leche.crear_lote(operador, fecha=HOY, ordene="manana", litros=D("120"))
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "50", producto="leche")
        assert v.total == 175_000
        ll = leche.con_totales(LoteLeche.objects.filter(pk=ll.pk)).get()
        assert ll.saldo_disponible == D("70")
        assert ventas_srv.leche_vendible(ll) == D("70")
        sesion(admin)
        with pytest.raises(ReglaNegocio):
            leche.anular_lote(admin, ll, "error de carga")
        with pytest.raises(ReglaNegocio, match="No hay stock suficiente"):
            vender(admin, clientes["almacen"], "71", producto="leche")

    def test_leche_de_hace_mas_de_tres_dias_no_se_vende(self, operador, ventas, sesion, clientes):
        sesion(operador)
        leche.crear_lote(operador, fecha=HOY - datetime.timedelta(days=3), ordene="manana", litros=D("100"))
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="hay 0 L"):
            vender(ventas, clientes["almacen"], "10", producto="leche")

    def test_no_sale_de_un_lote_elaborado_despues_de_la_venta(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="hay 11 kg"):
            vender(ventas, clientes["almacen"], "12", fecha=AYER)

    def test_reintento_con_el_mismo_id_no_duplica(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        ident = uuid.uuid4()
        v1, creada1 = ventas_srv.registrar_venta(ventas, cliente=clientes["almacen"], producto="queso",
                                                 cantidad=D("2"), id=ident)
        v2, creada2 = ventas_srv.registrar_venta(ventas, cliente=clientes["almacen"], producto="queso",
                                                 cantidad=D("2"), id=ident)
        assert creada1 and not creada2 and v1.pk == v2.pk
        assert stock_queso_kg() == D("19")

    def test_cliente_dado_de_baja_o_fecha_futura(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        with pytest.raises(ReglaNegocio, match="futura"):
            vender(ventas, clientes["almacen"], "1", fecha=HOY + datetime.timedelta(days=1))
        clientes["almacen"].activo = False
        clientes["almacen"].save()
        with pytest.raises(ReglaNegocio, match="dado de baja"):
            vender(ventas, clientes["almacen"], "1")


# --- Entrega, cobros y anulación ------------------------------------------------------------

@pytest.mark.django_db
class TestCobros:
    def test_entrega_y_cobro_en_partes_hasta_cobrada(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "2")  # 80.000
        ventas_srv.entregar(ventas, v)
        assert Venta.objects.get(pk=v.pk).estado_venta == "entregada"
        cuenta = v.cuenta
        ventas_srv.registrar_cobro(ventas, cuenta, monto=50_000)
        cuenta.refresh_from_db()
        assert cuenta.estado == "parcial" and cuenta.saldo == 30_000
        with pytest.raises(ReglaNegocio, match="no se puede cobrar más"):
            ventas_srv.registrar_cobro(ventas, cuenta, monto=30_001)
        ventas_srv.registrar_cobro(ventas, cuenta, monto=30_000, medio="transferencia")
        cuenta.refresh_from_db()
        assert cuenta.estado == "cobrada" and cuenta.saldo == 0
        assert Venta.objects.get(pk=v.pk).estado_venta == "cobrada"

    def test_venta_de_contado_entregada_y_cobrada_en_un_paso(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "1", entregada=True, cobrar_ahora=True)
        assert v.estado_venta == "cobrada" and v.cuenta.saldo == 0

    def test_anular_solo_admin_con_motivo_y_devuelve_el_stock(self, admin, ventas, sesion, clientes, quesos):
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "5", cobrar_ahora=True)
        assert stock_queso_kg() == D("16")
        with pytest.raises(ReglaNegocio, match="Solo el Administrador"):
            ventas_srv.anular_venta(ventas, v, "se equivocó")
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="motivo"):
            ventas_srv.anular_venta(admin, v, " ")
        with pytest.raises(ReglaNegocio, match="anulalos primero"):
            ventas_srv.anular_venta(admin, v, "Cliente devolvió")
        ventas_srv.anular_cobro(admin, v.cuenta.cobros.get(), "Cobro mal cargado")
        ventas_srv.anular_venta(admin, v, "Cliente devolvió")
        v.refresh_from_db()
        assert v.estado_venta == "anulada" and v.cuenta.estado == "anulada"
        assert stock_queso_kg() == D("21")
        assert MovimientoInventario.objects.filter(venta=v, motivo="devolucion").count() == 1

    def test_anular_venta_de_leche_devuelve_los_litros(self, operador, admin, ventas, sesion, clientes):
        sesion(operador)
        ll, _ = leche.crear_lote(operador, fecha=HOY, ordene="manana", litros=D("100"))
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "40", producto="leche")
        sesion(admin)
        ventas_srv.anular_venta(admin, v, "No se entregó")
        assert ventas_srv.leche_vendible(LoteLeche.objects.get(pk=ll.pk)) == D("100")
        vender(admin, clientes["almacen"], "100", producto="leche")


# --- Trazabilidad e historial ----------------------------------------------------------------

@pytest.mark.django_db
class TestTrazabilidad:
    def test_desde_el_lote_de_queso_se_ven_los_clientes(self, admin, ventas, sesion, clientes, quesos):
        viejo, nuevo = quesos
        sesion(ventas)
        vender(ventas, clientes["almacen"], "4")
        anulada = vender(ventas, clientes["super"], "2")
        vender(ventas, clientes["super"], "9")  # 5 que quedaban del viejo y 4 del nuevo
        sesion(admin)
        ventas_srv.anular_venta(admin, anulada, "Duplicada")
        t = queso.trazabilidad(LoteQueso.objects.get(pk=viejo.pk))
        assert [(c["nombre"], c["kg"]) for c in t["clientes"]] == [("Almacén Doña Rosa", D("4")), ("Super Central", D("5"))]
        assert [c["nombre"] for c in queso.trazabilidad(LoteQueso.objects.get(pk=nuevo.pk))["clientes"]] == ["Super Central"]

    def test_desde_el_cliente_se_ve_su_historial_y_los_lotes(self, ventas, sesion, clientes, quesos):
        viejo, nuevo = quesos
        sesion(ventas)
        vender(ventas, clientes["super"], "9")
        vender(ventas, clientes["super"], "5")
        h = ventas_srv.historial_cliente(clientes["super"])
        assert h["totales"]["compras"] == 2 and h["totales"]["kg_queso"] == D("14")
        assert h["totales"]["total_comprado"] == 14 * 36_000 and h["totales"]["saldo_pendiente"] == 14 * 36_000
        assert {(l["codigo"], l["cantidad"]) for l in h["lotes_entregados"]} == {(viejo.codigo, D("11")), (nuevo.codigo, D("3"))}

    def test_resumen_de_cuentas_por_cobrar(self, ventas, sesion, clientes, quesos):
        sesion(ventas)
        vender(ventas, clientes["almacen"], "1", fecha=AYER)  # contado de ayer sin cobrar: vencida
        vender(ventas, clientes["super"], "2")  # crédito 15 días
        r = ventas_srv.resumen_cuentas(HOY)
        assert r["total_por_cobrar"] == 40_000 + 72_000 and r["vencido"] == 40_000
        assert r["por_cliente"][0]["nombre"] == "Super Central"


# --- API y permisos --------------------------------------------------------------------------

@pytest.mark.django_db
class TestApiVentas:
    def test_ventas_crea_cliente_y_registra_venta_por_api(self, como, ventas, precios, quesos):
        op = como(ventas)
        r = op.post("/api/v1/clientes", {"nombre": "Despensa Mbói", "tipo": "minorista",
                                         "telefono": "0981 123 456", "condicion_pago": "credito_7"}, format="json")
        assert r.status_code == 201, r.data
        cliente = r.data["id"]
        c = op.get("/api/v1/precios/cotizar", {"cliente": cliente, "producto": "queso", "cantidad": "2.5"}).data
        assert c["precio_unitario"] == 40_000 and c["total"] == 100_000 and c["stock_disponible"] == D("21")
        ident = str(uuid.uuid4())
        datos = {"id": ident, "cliente": cliente, "producto": "queso", "cantidad": "2.5"}
        r = op.post("/api/v1/ventas", datos, format="json")
        assert r.status_code == 201 and r.data["total"] == 100_000 and r.data["cuenta"]["saldo"] == 100_000
        assert op.post("/api/v1/ventas", datos, format="json").status_code == 200  # reintento sin señal
        r = op.post("/api/v1/ventas", {**datos, "id": str(uuid.uuid4()), "cantidad": "30"}, format="json")
        assert r.status_code == 409 and "No hay stock suficiente" in r.data["detail"]
        h = op.get(f"/api/v1/clientes/{cliente}/historial").data
        assert h["totales"]["compras"] == 1 and len(h["lotes_entregados"]) == 1
        assert op.get("/api/v1/clientes", {"buscar": "mbói"}).data["results"][0]["saldo_pendiente"] == 100_000
        r = op.post(f"/api/v1/ventas/{ident}/cobrar", {"monto": 100_000}, format="json")
        assert r.status_code == 201 and r.data["cuenta"]["estado"] == "cobrada"

    def test_ventas_no_ve_los_reportes_financieros(self, como, ventas):
        op = como(ventas)
        assert op.get("/api/v1/cuentas-por-cobrar").status_code == 403
        assert op.get("/api/v1/cuentas-por-cobrar-resumen").status_code == 403

    def test_ventas_no_anula(self, como, ventas, sesion, clientes, quesos):
        sesion(ventas)
        v = vender(ventas, clientes["almacen"], "1")
        assert como(ventas).post(f"/api/v1/ventas/{v.pk}/anular", {"motivo": "x"}, format="json").status_code == 403

    def test_operador_solo_consulta(self, como, operador, ventas, sesion, clientes, quesos):
        sesion(ventas)
        vender(ventas, clientes["almacen"], "1")
        op = como(operador)
        assert op.get("/api/v1/ventas").data["count"] == 1
        assert op.get("/api/v1/clientes").status_code == 200
        assert op.post("/api/v1/clientes", {"nombre": "X"}, format="json").status_code == 403
        assert op.patch(f"/api/v1/clientes/{clientes['almacen'].pk}", {"nombre": "X"}, format="json").status_code == 403
        assert op.post("/api/v1/ventas", {"cliente": str(clientes["almacen"].pk), "producto": "queso",
                                          "cantidad": "1"}, format="json").status_code == 403
        assert op.get("/api/v1/cuentas-por-cobrar").status_code == 403

    def test_admin_ve_cuentas_y_anula_cobros(self, como, admin, ventas, sesion, clientes, quesos):
        sesion(ventas)
        v = vender(ventas, clientes["super"], "2", cobrar_ahora=True)
        ad = como(admin)
        cuentas = ad.get("/api/v1/cuentas-por-cobrar", {"estado": "todas"}).data["results"]
        assert len(cuentas) == 1 and cuentas[0]["estado"] == "cobrada"
        cobro = v.cuenta.cobros.get()
        r = ad.post(f"/api/v1/cuentas-por-cobrar/cobros/{cobro.pk}/anular", {"motivo": "Cheque rechazado"}, format="json")
        assert r.status_code == 200 and r.data["saldo"] == 72_000
        assert ad.get("/api/v1/cuentas-por-cobrar-resumen").data["total_por_cobrar"] == 72_000

    def test_trazabilidad_por_api_muestra_clientes(self, como, operador, ventas, sesion, clientes, quesos):
        viejo, _ = quesos
        sesion(ventas)
        vender(ventas, clientes["almacen"], "3")
        r = como(operador).get(f"/api/v1/lotes-queso/{viejo.pk}/trazabilidad")
        assert r.status_code == 200 and r.data["clientes"][0]["nombre"] == "Almacén Doña Rosa"
