"""Fase 6: tablero, reportes, exportables, bandeja de control y alertas.

El escenario carga un mes chico con números redondos y cada prueba compara el reporte contra
la cuenta hecha a mano y contra la suma directa de los registros (ventas, gastos, compras, cobros).
"""
import datetime
import io
from decimal import Decimal

import pytest
from django.db.models import Sum

from apps.compras import servicios as compras
from apps.compras.models import Compra, Pago, Proveedor
from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.gastos import servicios as gastos
from apps.gastos.models import Gasto
from apps.inventario import servicios as inventario
from apps.inventario.models import Insumo, Motivo
from apps.leche import servicios as leche
from apps.leche.models import LoteLeche
from apps.queso import servicios as queso
from apps.queso.models import LoteQueso
from apps.reportes import alertas, servicios as reportes
from apps.ventas import servicios as ventas_srv
from apps.ventas.models import Cliente, Cobro, Precio, Venta

D = Decimal
HOY = datetime.date(2026, 11, 26)
INICIO = datetime.date(2026, 11, 1)
OCT = datetime.date(2026, 10, 31)


@pytest.fixture(autouse=True)
def fecha_fija(monkeypatch, settings, tmp_path):
    monkeypatch.setattr(leche, "hoy", lambda: HOY)
    settings.GASTO_MONTO_APROBACION = 500_000
    settings.MEDIA_ROOT = tmp_path


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


def nov(dia):
    return datetime.date(2026, 11, dia)


@pytest.fixture
def mes(admin, operador, sesion):
    """Noviembre: 550 L, un lote de queso de 30 kg, dos ventas válidas y una anulada, gastos, compras y pagos."""
    sesion(admin)
    Precio.objects.create(producto="queso", precio_unitario=40_000)
    Precio.objects.create(producto="leche", precio_unitario=3_500)
    cliente = Cliente.objects.create(nombre="Almacén Doña Rosa", tipo="minorista")
    prov = Proveedor.objects.create(nombre="Lácteos Insumos", tipo="insumos")
    cuajo = Insumo.objects.create(codigo="CUAJO", nombre="Cuajo", categoria="cuajo", unidad="ml", stock_minimo=D("0"))
    sal = Insumo.objects.create(codigo="SAL", nombre="Sal", categoria="sal", unidad="kg")

    # Octubre (fuera del período): leche descartada y cerrada, una compra pagada y un gasto.
    oct_lote, _ = leche.crear_lote(admin, fecha=OCT, ordene="manana", litros=D("100"))
    leche.asignar_destino(admin, oct_lote, tipo="descarte", litros=D("100"))
    leche.cerrar_lote(admin, LoteLeche.objects.get(pk=oct_lote.pk))
    compras.registrar_compra(admin, proveedor=prov, fecha=datetime.date(2026, 10, 20), pagada=True,
                             items=[{"insumo": sal, "cantidad": D("10"), "precio_unitario": 5_000}])
    gastos.registrar_gasto(admin, fecha=OCT, categoria="otros", centro_costo="administracion", monto=100_000,
                           descripcion="Gasto de octubre")

    # Noviembre: compra de cuajo a crédito (80.000) y un pago parcial de 30.000.
    compra, _ = compras.registrar_compra(admin, proveedor=prov, fecha=nov(5), condicion="credito_30",
                                         items=[{"insumo": cuajo, "cantidad": D("1000"), "precio_unitario": 80}])
    compras.registrar_pago(admin, compra.cuenta, monto=30_000, fecha=nov(15))

    # Leche: 300 + 200 el día 10 y 50 hoy.
    manana, _ = leche.crear_lote(admin, fecha=nov(10), ordene="manana", litros=D("300"))
    tarde, _ = leche.crear_lote(admin, fecha=nov(10), ordene="tarde", litros=D("200"))
    leche.crear_lote(admin, fecha=HOY, ordene="manana", litros=D("50"))

    # Queso: 300 L de la mañana, 100 ml de cuajo, 30 kg (10 L/kg).
    sesion(operador)
    lq, _ = queso.iniciar_lote(operador, fecha=nov(10), origenes=[{"lote_leche": manana, "litros": D("300")}],
                               insumos=[{"insumo": cuajo, "cantidad": D("100")}])
    lq = queso.cerrar_lote(operador, LoteQueso.objects.get(pk=lq.pk), kg_obtenidos=D("30"))
    sesion(admin)
    lq = queso.aprobar_lote(admin, lq, "Buen lote")

    # Gastos: dos chicos (se aprueban solos), uno grande que aprueba el Administrador y uno que queda pendiente.
    sesion(operador)
    gastos.registrar_gasto(operador, fecha=nov(3), categoria="sanidad", centro_costo="produccion_leche",
                           monto=400_000, descripcion="Vacunas")
    gastos.registrar_gasto(operador, fecha=nov(4), categoria="mantenimiento", centro_costo="elaboracion_queso",
                           monto=150_000, descripcion="Arreglo de la tina")
    grande, _ = gastos.registrar_gasto(operador, fecha=nov(6), categoria="honorarios", centro_costo="administracion",
                                       monto=900_000, descripcion="Contador")
    gastos.registrar_gasto(operador, fecha=nov(7), categoria="alimentacion", centro_costo="produccion_leche",
                           monto=700_000, descripcion="Balanceado (sin aprobar)")
    sesion(admin)
    gastos.aprobar_gasto(admin, Gasto.objects.get(pk=grande.pk), "Ok")

    # Ventas: 10 kg de queso cobrados, 50 L de leche cobrados en parte, y una venta anulada.
    vq, _ = ventas_srv.registrar_venta(admin, cliente=cliente, producto="queso", cantidad=D("10"), fecha=nov(12))
    ventas_srv.registrar_cobro(admin, vq.cuenta, monto=400_000, fecha=nov(12))
    vl, _ = ventas_srv.registrar_venta(admin, cliente=cliente, producto="leche", cantidad=D("50"), fecha=nov(12))
    ventas_srv.registrar_cobro(admin, vl.cuenta, monto=100_000, fecha=nov(14))
    va, _ = ventas_srv.registrar_venta(admin, cliente=cliente, producto="queso", cantidad=D("5"), fecha=nov(13))
    ventas_srv.anular_venta(admin, Venta.objects.get(pk=va.pk), "Cargada por error")
    return {"lote_queso": LoteQueso.objects.get(pk=lq.pk), "cuajo": cuajo, "lote_oct": oct_lote, "compra": compra}


# Valores calculados a mano para el escenario.
COSTO_LITRO = D(400_000) / D(550)                     # gastos de producción ÷ litros del mes
COSTO_LOTE = round(300 * COSTO_LITRO) + 100 * 80 + 150_000   # leche + cuajo + elaboración = 376.182


@pytest.mark.django_db
class TestCuadre:
    def test_estado_de_resultados_cuadra_con_ventas_gastos_y_compras(self, mes):
        r = reportes.estado_resultados(INICIO, HOY)
        ventas = Venta.objects.exclude(estado_venta="anulada").filter(fecha__range=(INICIO, HOY)).aggregate(t=Sum("total"))["t"]
        aprobados = Gasto.objects.filter(estado="aprobado", fecha__range=(INICIO, HOY)).aggregate(t=Sum("monto"))["t"]
        compras_mes = Compra.objects.filter(estado_compra="confirmada", fecha__range=(INICIO, HOY)).aggregate(t=Sum("total"))["t"]
        assert (ventas, aprobados, compras_mes) == (575_000, 1_450_000, 80_000)
        assert r["total_ingresos"] == ventas == 575_000
        assert {i["producto"]: i["monto"] for i in r["ingresos"]} == {"queso": 400_000, "leche": 175_000}
        assert r["total_gastos"] == aprobados
        assert sum(g["total"] for g in r["gastos_por_categoria"]) == sum(g["total"] for g in r["gastos_por_centro"]) == aprobados
        assert r["compras_insumos"] == compras_mes
        assert r["resultado"] == 575_000 - 1_450_000 - 80_000 == -955_000
        # Lo pendiente y lo anulado no entra, pero se informa lo pendiente.
        assert r["gastos_pendientes"] == {"total": 700_000, "cantidad": 1}

    def test_octubre_queda_fuera_y_tiene_su_propio_resultado(self, mes):
        r = reportes.estado_resultados(datetime.date(2026, 10, 1), OCT)
        assert r["total_ingresos"] == 0
        assert r["total_gastos"] == 100_000
        assert r["compras_insumos"] == 50_000
        assert r["resultado"] == -150_000

    def test_flujo_de_caja_diario_y_mensual(self, mes):
        dia = reportes.flujo_caja(INICIO, HOY, "dia")
        cobros = Cobro.objects.filter(anulado=False, fecha__range=(INICIO, HOY)).aggregate(t=Sum("monto"))["t"]
        pagos = Pago.objects.filter(anulado=False, fecha__range=(INICIO, HOY)).aggregate(t=Sum("monto"))["t"]
        assert (cobros, pagos) == (500_000, 30_000)
        assert dia["totales"] == {"cobros": 500_000, "pagos_proveedores": 30_000, "gastos": 1_450_000,
                                  "salidas": 1_480_000, "neto": -980_000}
        assert dia["filas"][-1]["acumulado"] == -980_000
        assert [f["periodo"] for f in dia["filas"]] == sorted(f["periodo"] for f in dia["filas"])
        del_12 = next(f for f in dia["filas"] if f["periodo"] == nov(12))
        assert del_12["cobros"] == 400_000
        mensual = reportes.flujo_caja(datetime.date(2026, 10, 1), HOY, "mes")
        assert [f["periodo"] for f in mensual["filas"]] == [datetime.date(2026, 10, 1), INICIO]
        octubre, noviembre = mensual["filas"]
        assert octubre["pagos_proveedores"] == 50_000 and octubre["gastos"] == 100_000
        assert {k: noviembre[k] for k in dia["totales"]} == dia["totales"]

    def test_costo_y_rentabilidad_del_lote(self, mes):
        r = reportes.rentabilidad_lotes(INICIO, HOY)
        assert len(r["lotes"]) == 1
        l = r["lotes"][0]
        assert l["costo_leche"] == round(300 * COSTO_LITRO) == 218_182
        assert l["costo_insumos"] == 8_000            # 100 ml × Gs. 80
        assert l["costo_elaboracion"] == 150_000      # todos los gastos de elaboración del mes (único lote)
        assert l["costo_total"] == COSTO_LOTE == 376_182
        assert l["costo_kg"] == 12_539
        assert l["kg_vendidos"] == D("10") and l["kg_sin_vender"] == D("20")
        assert l["ingresos"] == 400_000               # la venta anulada no cuenta
        assert l["resultado"] == 400_000 - 376_182
        assert l["costo_de_lo_vendido"] == round(D(376_182) * 10 / 30) == 125_394
        assert l["insumos_sin_precio"] == []

    def test_margen_por_producto(self, mes):
        r = reportes.rentabilidad_productos(INICIO, HOY)
        p = {x["producto"]: x for x in r["productos"]}
        assert p["leche"]["ingresos"] == 175_000
        assert p["leche"]["costo"] == round(50 * COSTO_LITRO) == 36_364
        assert p["leche"]["margen"] == 175_000 - 36_364
        assert p["queso"]["ingresos"] == 400_000
        assert p["queso"]["costo"] == round(D(376_182) / 30 * 10) == 125_394
        assert r["total"]["ingresos"] == reportes.estado_resultados(INICIO, HOY)["total_ingresos"]
        assert r["gastos_administracion"] == 900_000

    def test_tablero_coincide_con_los_reportes(self, mes):
        op = reportes.tablero_operativo(HOY)
        assert op["leche"]["hoy"] == D("50") and op["leche"]["mes"] == D("550")
        assert op["queso"]["mes_kg"] == D("30") and op["queso"]["hoy_kg"] == D("0")
        assert op["queso"]["rendimiento_mes"] == D("10.00")
        assert sum(d["litros"] for d in op["leche"]["ultimos_30"]) == D("650")  # incluye los 100 L de octubre
        fin = reportes.tablero_financiero(HOY)
        er = reportes.estado_resultados(INICIO, HOY)
        assert fin["ingresos_mes"] == {"leche": 175_000, "queso": 400_000, "total": 575_000}
        assert fin["gastos_mes"]["total"] == er["total_gastos"]
        assert fin["resultado_mes"] == er["resultado"]
        assert fin["cuentas"]["por_cobrar"] == {"total": 75_000, "vencido": 75_000, "cuentas": 1, "vencidas": 1}
        assert fin["cuentas"]["por_pagar"] == {"total": 50_000, "vencido": 0, "cuentas": 1, "vencidas": 0}

    def test_insumo_sin_compras_no_suma_costo_y_se_avisa(self, mes, admin, operador, sesion):
        sesion(admin)
        fermento = Insumo.objects.create(codigo="FERM", nombre="Fermento", categoria="cultivo", unidad="g")
        inventario.entrada(admin, fermento, D("100"), motivo=Motivo.AJUSTE, nota="Stock inicial")
        ll, _ = leche.crear_lote(admin, fecha=nov(20), ordene="manana", litros=D("100"))
        sesion(operador)
        lq, _ = queso.iniciar_lote(operador, fecha=nov(20), origenes=[{"lote_leche": ll, "litros": D("100")}],
                                   insumos=[{"insumo": fermento, "cantidad": D("5")}])
        queso.cerrar_lote(operador, LoteQueso.objects.get(pk=lq.pk), kg_obtenidos=D("10"))
        fila = next(l for l in reportes.rentabilidad_lotes(INICIO, HOY)["lotes"] if l["fecha"] == nov(20))
        assert fila["costo_insumos"] == 0
        assert fila["insumos_sin_precio"] == ["Fermento"]


@pytest.mark.django_db
class TestPermisos:
    RUTAS_FINANCIERAS = ["reportes/estado-resultados", "reportes/flujo-caja", "reportes/rentabilidad-lotes",
                         "reportes/rentabilidad-productos", "reportes/estado-resultados.pdf",
                         "reportes/rentabilidad-lotes.xlsx"]

    def test_operador_ve_produccion_pero_no_plata(self, como, operador, mes):
        api = como(operador)
        r = api.get("/api/v1/tablero")
        assert r.status_code == 200
        assert "financiero" not in r.data and "pendientes" not in r.data
        assert r.data["operativo"]["leche"]["mes"] == D("550")
        assert all(a["tipo"] != "cuenta_vencida" for a in r.data["alertas"])
        for ruta in self.RUTAS_FINANCIERAS + ["reportes/aprobaciones", "control/registros-editados"]:
            assert api.get(f"/api/v1/{ruta}").status_code == 403, ruta

    def test_ventas_no_entra_al_tablero(self, como, ventas):
        assert como(ventas).get("/api/v1/tablero").status_code == 403

    def test_admin_ve_todo(self, como, admin, mes):
        api = como(admin)
        r = api.get("/api/v1/tablero")
        assert r.data["financiero"]["resultado_mes"] == -955_000
        assert r.data["pendientes"]["gastos"] == 1
        for ruta in self.RUTAS_FINANCIERAS:
            assert api.get(f"/api/v1/{ruta}").status_code == 200, ruta

    def test_periodo_invalido(self, como, admin):
        r = como(admin).get("/api/v1/reportes/estado-resultados?desde=2026-11-20&hasta=2026-11-01")
        assert r.status_code == 400


@pytest.mark.django_db
class TestExportables:
    @pytest.mark.parametrize("nombre", ["estado-resultados", "flujo-caja", "flujo-caja-mensual", "rentabilidad-lotes",
                                        "rentabilidad-productos", "aprobaciones"])
    def test_pdf_y_excel(self, como, admin, mes, nombre):
        api = como(admin)
        pdf = api.get(f"/api/v1/reportes/{nombre}.pdf?desde=2026-11-01&hasta=2026-11-26")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert pdf["Content-Type"] == "application/pdf"
        assert "attachment" in pdf["Content-Disposition"]
        xlsx = api.get(f"/api/v1/reportes/{nombre}.xlsx?desde=2026-11-01&hasta=2026-11-26")
        assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")

    def test_excel_trae_los_mismos_numeros(self, como, admin, mes):
        from openpyxl import load_workbook

        r = como(admin).get("/api/v1/reportes/estado-resultados.xlsx?desde=2026-11-01&hasta=2026-11-26")
        hoja = load_workbook(io.BytesIO(r.content)).active
        valores = {fila[0]: fila[1] for fila in hoja.iter_rows(values_only=True) if fila and fila[0]}
        assert valores["Total ingresos"] == 575_000
        assert valores["Total egresos"] == -1_530_000
        assert valores["Resultado del período"] == -955_000
        assert valores["Compras de insumos"] == -80_000

    def test_formato_o_reporte_desconocido(self, como, admin):
        assert como(admin).get("/api/v1/reportes/inventado.pdf").status_code == 404
        assert como(admin).get("/api/v1/reportes/estado-resultados.csv").status_code == 404


@pytest.mark.django_db
class TestControl:
    def test_historial_de_aprobaciones(self, mes, admin):
        filas = reportes.historial_aprobaciones(INICIO, HOY)
        del_admin = [f for f in filas if f["usuario"] == admin.nombre and f["accion"] == "aprobar"]
        entidades = {f["entidad"] for f in del_admin}
        assert {"gastos", "lotes_queso"} <= entidades
        contador = next(f for f in del_admin if f["entidad"] == "gastos")
        assert "Contador" in contador["registro"] and contador["motivo"] == "Ok"
        automaticas = [f for f in filas if f["accion_nombre"] == "Aprobó automáticamente"]
        # Los dos gastos chicos de noviembre y el de octubre (la fecha es la de la aprobación, que fue hoy).
        assert len(automaticas) == 3
        assert all(f["usuario"].startswith("Automática (cargó") for f in automaticas)
        assert len(filas) == len({(f["entidad"], f["registro"], f["accion"]) for f in filas})  # sin duplicados
        assert [f["fecha"] for f in filas] == sorted((f["fecha"] for f in filas), reverse=True)

    def test_edicion_de_registro_cerrado_aparece_hasta_que_se_revisa(self, mes, admin, sesion, como):
        sesion(admin)
        leche.editar_lote(admin, LoteLeche.objects.get(pk=mes["lote_oct"].pk), {"observaciones": "Corregido"},
                          motivo="Faltaba la nota")
        filas = reportes.registros_editados(solo_sin_revisar=True)
        assert len(filas) == 1
        assert filas[0]["accion"] == "editar_bloqueado" and filas[0]["motivo"] == "Faltaba la nota"
        assert filas[0]["registro"].startswith("LL-20261031-M")
        assert reportes.pendientes_control()["registros_editados"] == 1
        r = como(admin).post(f"/api/v1/control/registros-editados/{filas[0]['id']}/revisar", {"nota": "Visto"}, format="json")
        assert r.status_code == 200
        assert reportes.registros_editados(solo_sin_revisar=True) == []
        assert reportes.registros_editados()[0]["revisado"]["nota"] == "Visto"

    def test_anular_un_cobro_queda_para_auditar(self, mes, admin, sesion):
        sesion(admin)
        cobro = Cobro.objects.filter(monto=100_000).get()
        ventas_srv.anular_cobro(admin, cobro, "Se cargó dos veces")
        assert [f["accion"] for f in reportes.registros_editados()] == ["anular_cobro"]


@pytest.mark.django_db
class TestAlertas:
    def test_por_defecto_salen_del_env(self, db, settings):
        assert alertas.leer()["rendimiento"] == {"activa": True, "minimo": settings.QUESO_RENDIMIENTO_MIN_L_KG,
                                                  "maximo": settings.QUESO_RENDIMIENTO_MAX_L_KG}

    def test_configurar_y_disparar(self, mes, admin, sesion, como):
        api = como(admin)
        r = api.put("/api/v1/alertas/configuracion", {
            "produccion_baja": {"activa": True, "litros_minimos": 400},
            "rendimiento": {"minimo": 11, "maximo": 14},
        }, format="json")
        assert r.status_code == 200, r.content
        assert queso.rango_rendimiento() == (D("11"), D("14"))
        assert leche.umbral_litros_diarios() == D("400")
        sesion(admin)
        Insumo.objects.filter(pk=mes["cuajo"].pk).update(stock_minimo=D("2000"))
        tipos = [a["tipo"] for a in reportes.calcular_alertas(HOY)]
        assert tipos.count("produccion_baja") == 6        # del 20 al 25 sin ordeñe; hoy no cuenta (incompleto)
        assert tipos.count("rendimiento") == 1            # 10 L/kg fuera de 11–14
        assert tipos.count("stock_bajo") == 1             # cuajo: 900 ml contra 2000
        assert tipos.count("cuenta_vencida") == 1         # la leche de contado sin cobrar del todo
        assert "cuenta_vencida" not in [a["tipo"] for a in reportes.calcular_alertas(HOY, financieras=False)]

    def test_apagar_y_dias_de_gracia(self, mes, admin):
        alertas.guardar(admin, {"stock_bajo": {"activa": False}, "cuentas_vencidas": {"dias_gracia": 30}})
        Insumo.objects.filter(pk=mes["cuajo"].pk).update(stock_minimo=D("2000"))
        tipos = {a["tipo"] for a in reportes.calcular_alertas(HOY)}
        assert "stock_bajo" not in tipos and "cuenta_vencida" not in tipos

    def test_validaciones_y_permiso(self, como, admin, operador):
        api = como(admin)
        assert api.put("/api/v1/alertas/configuracion", {"rendimiento": {"minimo": 12, "maximo": 9}},
                       format="json").status_code == 409
        assert api.put("/api/v1/alertas/configuracion", {"inventada": {"activa": True}}, format="json").status_code == 409
        op = como(operador)
        assert op.get("/api/v1/alertas/configuracion").status_code == 200
        assert op.put("/api/v1/alertas/configuracion", {"stock_bajo": {"activa": False}}, format="json").status_code == 403
