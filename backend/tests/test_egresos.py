"""Fase 5: proveedores, gastos con aprobación según el monto, comprobantes y compras de insumos."""
import datetime
import uuid
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.compras import servicios as compras
from apps.compras.models import CuentaPorPagar, Proveedor
from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.mixins import ReglaNegocio
from apps.core.models import Auditoria
from apps.gastos import servicios as gastos
from apps.gastos.models import Gasto
from apps.inventario import servicios as inventario
from apps.inventario.models import Insumo, MovimientoInventario
from apps.leche import servicios as leche

HOY = datetime.date(2026, 11, 26)
D = Decimal
# PNG de 1x1 píxel.
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture(autouse=True)
def entorno(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(leche, "hoy", lambda: HOY)
    settings.MEDIA_ROOT = tmp_path
    settings.GASTO_MONTO_APROBACION = 500_000


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


def gasto(usuario, monto, **extra):
    datos = {"categoria": "sanidad", "centro_costo": "produccion_leche", "descripcion": "Vacunas", "monto": monto}
    datos.update(extra)
    g, _ = gastos.registrar_gasto(usuario, **datos)
    return Gasto.objects.get(pk=g.pk)


def foto(nombre="ticket.png", contenido=PNG, tipo="image/png"):
    return SimpleUploadedFile(nombre, contenido, content_type=tipo)


# --- Gastos ----------------------------------------------------------------------------------

@pytest.mark.django_db
class TestGastos:
    def test_bajo_el_umbral_se_aprueba_solo(self, operador, sesion):
        sesion(operador)
        g = gasto(operador, 500_000)
        assert g.estado == "aprobado" and g.aprobacion_automatica
        assert "automáticamente" in g.motivo_estado

    def test_sobre_el_umbral_queda_pendiente_y_aparece_en_la_bandeja(self, operador, sesion):
        sesion(operador)
        g = gasto(operador, 500_001)
        assert g.estado == "pendiente" and not g.aprobacion_automatica
        assert gastos.pendientes_de_aprobacion()["gastos"] == 1

    def test_el_administrador_aprueba_y_queda_quien_y_cuando(self, admin, operador, sesion):
        sesion(operador)
        g = gasto(operador, 1_200_000)
        with pytest.raises(ReglaNegocio, match="Solo el Administrador"):
            gastos.aprobar_gasto(operador, g)
        sesion(admin)
        g = gastos.aprobar_gasto(admin, g, "Ok, factura vista")
        assert g.estado == "aprobado" and g.aprobado_por == admin and g.fecha_aprobacion is not None
        fila = Auditoria.objects.filter(accion="aprobar", entidad="gastos", entidad_id=str(g.pk)).get()
        assert fila.usuario == admin and fila.motivo == "Ok, factura vista"

    def test_rechazo_con_comentario_y_correccion(self, admin, operador, sesion):
        sesion(operador)
        g = gasto(operador, 900_000)
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="comentario"):
            gastos.rechazar_gasto(admin, g, " ")
        g = gastos.rechazar_gasto(admin, g, "El monto no coincide con la factura")
        assert g.estado == "rechazado" and g.motivo_estado == "El monto no coincide con la factura"
        sesion(operador)
        with pytest.raises(ReglaNegocio, match="Solo quien cargó"):
            gastos.corregir_gasto(admin, g, monto=800_000)
        g = gastos.corregir_gasto(operador, g, monto=450_000)
        assert g.estado == "aprobado" and g.aprobacion_automatica  # bajó del umbral

    def test_si_lo_carga_el_administrador_queda_aprobado(self, admin, sesion):
        sesion(admin)
        g = gasto(admin, 3_000_000)
        assert g.estado == "aprobado" and not g.aprobacion_automatica and g.aprobado_por == admin

    def test_validaciones(self, operador, sesion):
        sesion(operador)
        with pytest.raises(ReglaNegocio, match="futura"):
            gasto(operador, 1000, fecha=HOY + datetime.timedelta(days=1))
        with pytest.raises(ReglaNegocio, match="en qué se gastó"):
            gasto(operador, 1000, descripcion=" ")

    def test_anular_solo_admin_con_motivo(self, admin, operador, sesion):
        sesion(operador)
        g = gasto(operador, 100_000)
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="motivo"):
            gastos.anular_gasto(admin, g, "")
        assert gastos.anular_gasto(admin, g, "Cargado dos veces").estado == "anulado"

    def test_resumen_por_categoria_y_centro(self, admin, operador, sesion):
        sesion(operador)
        gasto(operador, 100_000)
        gasto(operador, 200_000, categoria="combustible", centro_costo="administracion")
        gasto(operador, 900_000)  # pendiente: no suma
        r = gastos.resumen(admin)
        assert r["total_aprobado"] == 300_000 and r["pendientes"] == 1 and r["total_pendiente"] == 900_000
        assert r["por_categoria"][0] == {"categoria": "combustible", "total": 200_000, "cantidad": 1}


@pytest.mark.django_db
class TestApiGastos:
    def test_operador_ve_solo_los_suyos_admin_ve_todos(self, como, admin, operador, ventas, sesion):
        sesion(ventas)
        ajeno = gasto(ventas, 50_000, descripcion="Nafta reparto")
        sesion(operador)
        gasto(operador, 700_000, descripcion="Balanceado")
        op = como(operador)
        assert [g["descripcion"] for g in op.get("/api/v1/gastos").data["results"]] == ["Balanceado"]
        assert op.get(f"/api/v1/gastos/{ajeno.pk}").status_code == 404
        assert como(admin).get("/api/v1/gastos").data["count"] == 2
        assert como(admin).get("/api/v1/gastos", {"estado": "pendiente"}).data["count"] == 1

    def test_carga_con_foto_desde_el_celular_y_se_ve_en_la_ficha(self, como, admin, operador):
        op = como(operador)
        ident = str(uuid.uuid4())
        datos = {"id": ident, "categoria": "mantenimiento", "centro_costo": "elaboracion_queso", "monto": "750000",
                 "descripcion": "Arreglo de la tina", "comprobante_numero": "001-001-0001234", "comprobante": foto()}
        r = op.post("/api/v1/gastos", datos, format="multipart")
        assert r.status_code == 201, r.data
        assert r.data["estado"] == "pendiente" and r.data["tiene_comprobante"] and r.data["tipo_comprobante"] == "imagen"
        # Reenvío sin señal: no duplica.
        assert op.post("/api/v1/gastos", {**datos, "comprobante": foto()}, format="multipart").status_code == 200
        assert Gasto.objects.count() == 1
        for cliente in (op, como(admin)):
            f = cliente.get(f"/api/v1/gastos/{ident}/comprobante")
            assert f.status_code == 200 and f["Content-Type"] == "image/png"
            assert b"".join(f.streaming_content) == PNG
        # Aprobación por la bandeja
        ad = como(admin)
        assert ad.get("/api/v1/aprobaciones/pendientes").data["gastos"] == 1
        assert op.post(f"/api/v1/gastos/{ident}/aprobar", {}, format="json").status_code == 403
        r = ad.post(f"/api/v1/gastos/{ident}/aprobar", {"comentario": "Visto"}, format="json")
        assert r.status_code == 200 and r.data["aprobado_por_nombre"] == "Admin"

    def test_comprobante_invalido_es_rechazado(self, como, operador):
        datos = {"categoria": "otros", "centro_costo": "administracion", "monto": "1000", "descripcion": "x",
                 "comprobante": foto("virus.exe", b"MZ\x90\x00", "application/octet-stream")}
        r = como(operador).post("/api/v1/gastos", datos, format="multipart")
        assert r.status_code == 409 and "foto" in r.data["detail"]
        falso = {**datos, "comprobante": foto("foto.png", b"<html>no soy foto</html>", "image/png")}
        assert como(operador).post("/api/v1/gastos", falso, format="multipart").status_code == 409
        assert Gasto.objects.count() == 0

    def test_ventas_carga_gastos_pero_no_aprueba_ni_ve_la_bandeja(self, como, ventas):
        v = como(ventas)
        r = v.post("/api/v1/gastos", {"categoria": "combustible", "centro_costo": "administracion", "monto": "60000",
                                      "descripcion": "Nafta"}, format="json")
        assert r.status_code == 201 and r.data["estado"] == "aprobado"
        assert v.get("/api/v1/aprobaciones/pendientes").status_code == 403


# --- Proveedores y compras -------------------------------------------------------------------

@pytest.fixture
def base(admin, sesion):
    sesion(admin)
    prov = Proveedor.objects.create(nombre="Agroveterinaria San Juan", tipo="insumos")
    cuajo = Insumo.objects.create(codigo="CUAJO", nombre="Cuajo líquido", categoria="cuajo", unidad="ml")
    sal = Insumo.objects.create(codigo="SAL", nombre="Sal fina", categoria="sal", unidad="kg")
    return prov, cuajo, sal


def stock(insumo):
    return inventario.stock_de(insumo)["stock"]


@pytest.mark.django_db
class TestCompras:
    def test_confirmar_aumenta_el_inventario_y_genera_la_cuenta(self, operador, sesion, base):
        prov, cuajo, sal = base
        sesion(operador)
        c, _ = compras.registrar_compra(operador, proveedor=prov, condicion="credito_30", factura="001-002-555", items=[
            {"insumo": cuajo, "cantidad": D("1000"), "precio_unitario": 95, "lote_proveedor": "CJ-77"},
            {"insumo": sal, "cantidad": D("25"), "precio_unitario": 3_200},
        ])
        assert c.codigo == "C-00001" and c.total == 95_000 + 80_000
        assert stock(cuajo) == D("1000") and stock(sal) == D("25")
        movs = MovimientoInventario.objects.filter(compra=c, tipo="entrada", motivo="compra")
        assert movs.count() == 2 and movs.get(insumo=cuajo).lote_proveedor == "CJ-77"
        cuenta = c.cuenta
        assert cuenta.monto == 175_000 and cuenta.estado == "pendiente"
        assert cuenta.vencimiento == HOY + datetime.timedelta(days=30)

    def test_contado_pagado_en_el_momento(self, operador, sesion, base):
        prov, cuajo, _ = base
        sesion(operador)
        c, _ = compras.registrar_compra(operador, proveedor=prov, pagada=True,
                                        items=[{"insumo": cuajo, "cantidad": D("500"), "precio_unitario": 100}])
        assert CuentaPorPagar.objects.get(compra=c).estado == "pagada"

    def test_validaciones_y_nada_a_medias(self, operador, sesion, base):
        prov, cuajo, sal = base
        sesion(operador)
        with pytest.raises(ReglaNegocio, match="repetido"):
            compras.registrar_compra(operador, proveedor=prov, items=[
                {"insumo": cuajo, "cantidad": 1, "precio_unitario": 1}, {"insumo": cuajo, "cantidad": 1, "precio_unitario": 1}])
        sal.activo = False
        sal.save()
        with pytest.raises(ReglaNegocio, match="dado de baja"):
            compras.registrar_compra(operador, proveedor=prov, items=[
                {"insumo": cuajo, "cantidad": 1, "precio_unitario": 1}, {"insumo": sal, "cantidad": 1, "precio_unitario": 1}])
        assert stock(cuajo) == 0 and CuentaPorPagar.objects.count() == 0

    def test_pagos_solo_admin(self, admin, operador, sesion, base):
        prov, cuajo, _ = base
        sesion(operador)
        c, _ = compras.registrar_compra(operador, proveedor=prov, condicion="credito_15",
                                        items=[{"insumo": cuajo, "cantidad": D("100"), "precio_unitario": 1_000}])
        with pytest.raises(ReglaNegocio, match="Solo el Administrador"):
            compras.registrar_pago(operador, c.cuenta, monto=1)
        sesion(admin)
        compras.registrar_pago(admin, c.cuenta, monto=40_000, medio="transferencia")
        with pytest.raises(ReglaNegocio, match="no se puede pagar más"):
            compras.registrar_pago(admin, c.cuenta, monto=60_001)
        compras.registrar_pago(admin, c.cuenta, monto=60_000)
        c.cuenta.refresh_from_db()
        assert c.cuenta.estado == "pagada" and compras.resumen_cuentas(HOY)["pagado_mes"] == 100_000

    def test_anular_devuelve_el_stock_y_no_si_ya_se_uso(self, admin, operador, sesion, base):
        prov, cuajo, sal = base
        sesion(operador)
        c1, _ = compras.registrar_compra(operador, proveedor=prov, items=[{"insumo": cuajo, "cantidad": D("100"), "precio_unitario": 90}])
        c2, _ = compras.registrar_compra(operador, proveedor=prov, items=[{"insumo": sal, "cantidad": D("10"), "precio_unitario": 3000}])
        sesion(admin)
        inventario.salida_por_ajuste(admin, sal, D("4"), nota="Se humedeció")
        compras.anular_compra(admin, c1, "Factura equivocada")
        assert stock(cuajo) == 0 and c1.cuenta.__class__.objects.get(pk=c1.cuenta.pk).estado == "anulada"
        with pytest.raises(ReglaNegocio, match="ya se usó"):
            compras.anular_compra(admin, c2, "Error")
        assert stock(sal) == D("6")


@pytest.mark.django_db
class TestApiCompras:
    def test_operador_registra_proveedor_y_compra_por_api(self, como, admin, operador, base):
        _, cuajo, _ = base
        op = como(operador)
        r = op.post("/api/v1/proveedores", {"nombre": "Lácteos del Sur", "tipo": "insumos", "telefono": "0991 555"}, format="json")
        assert r.status_code == 201
        assert op.post("/api/v1/proveedores", {"nombre": "lácteos  del sur"}, format="json").status_code == 400
        prov = r.data["id"]
        r = op.post("/api/v1/compras", {"proveedor": prov, "condicion": "credito_15", "items": [
            {"insumo": str(cuajo.pk), "cantidad": "2000", "precio_unitario": 90}]}, format="json")
        assert r.status_code == 201 and r.data["total"] == 180_000 and r.data["cuenta"]["saldo"] == 180_000
        assert op.get(f"/api/v1/proveedores/{prov}").data["saldo_pendiente"] == 180_000
        compra = r.data["id"]
        r = op.post(f"/api/v1/compras/{compra}/comprobante", {"comprobante": foto()}, format="multipart")
        assert r.status_code == 200 and r.data["tiene_comprobante"]
        assert op.get(f"/api/v1/compras/{compra}/comprobante").status_code == 200
        # Pagar y ver cuentas por pagar: solo el Administrador
        assert op.post(f"/api/v1/compras/{compra}/pagar", {"monto": 1000}, format="json").status_code == 403
        assert op.get("/api/v1/cuentas-por-pagar").status_code == 403
        ad = como(admin)
        assert ad.post(f"/api/v1/compras/{compra}/pagar", {"monto": 80_000}, format="json").status_code == 201
        assert ad.get("/api/v1/cuentas-por-pagar-resumen").data["total_por_pagar"] == 100_000

    def test_ventas_no_entra_a_compras(self, como, ventas):
        v = como(ventas)
        assert v.get("/api/v1/compras").status_code == 403
        assert v.post("/api/v1/proveedores", {"nombre": "X"}, format="json").status_code == 403

    def test_menu_muestra_los_modulos_de_la_fase_5(self, como, admin, operador):
        disp = {m["codigo"] for m in como(admin).get("/api/v1/auth/me").data["modulos"] if m["disponible"]}
        assert {"compras", "gastos", "aprobaciones", "usuarios"} <= disp
        op = {m["codigo"] for m in como(operador).get("/api/v1/auth/me").data["modulos"]}
        assert "aprobaciones" not in op and {"compras", "gastos"} <= op


