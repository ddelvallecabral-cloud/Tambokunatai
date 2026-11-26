"""Fase 3: inventario, elaboración de queso, aprobación y trazabilidad."""
import datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import override_settings

from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.models import Auditoria
from apps.cuentas.models import Permiso, Rol, UsuarioRol
from apps.inventario import servicios as inventario
from apps.inventario.models import Insumo, MovimientoInventario
from apps.leche import servicios as leche
from apps.leche.models import DestinoLeche, LoteLeche
from apps.queso import servicios as queso
from apps.queso.models import LoteQueso
from apps.core.mixins import ReglaNegocio

from .conftest import crear_usuario

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
def insumos(admin, sesion):
    """Cuajo (ml) con 500 en stock y sal (kg) con 10."""
    sesion(admin)
    cuajo = Insumo.objects.create(codigo="CUAJO", nombre="Cuajo líquido", categoria="cuajo", unidad="ml",
                                  stock_minimo=D("100"))
    sal = Insumo.objects.create(codigo="SAL", nombre="Sal fina", categoria="sal", unidad="kg")
    inventario.entrada(admin, cuajo, D("500"), lote_proveedor="CJ-2611")
    inventario.entrada(admin, sal, D("10"))
    return cuajo, sal


def stock(insumo):
    return inventario.stock_de(insumo)


def lote_leche(usuario, fecha=HOY, ordene="manana", litros="100", destino="pendiente"):
    l, _ = leche.crear_lote(usuario, fecha=fecha, ordene=ordene, litros=D(litros), destino=destino)
    return LoteLeche.objects.get(pk=l.pk)


def iniciar(usuario, origenes, insumos_=(), fecha=HOY):
    lote, _ = queso.iniciar_lote(
        usuario, fecha=fecha,
        origenes=[{"lote_leche": l, "litros": D(x)} for l, x in origenes],
        insumos=[{"insumo": i, "cantidad": D(c)} for i, c in insumos_],
    )
    return LoteQueso.objects.get(pk=lote.pk)


# --- Inventario ------------------------------------------------------------------------------

@pytest.mark.django_db
class TestInventarioInsumos:
    def test_entrada_suma_stock_y_queda_auditada(self, insumos):
        cuajo, _ = insumos
        assert stock(cuajo) == {"stock": D("500"), "reservado": 0, "disponible": D("500")}
        mov = MovimientoInventario.objects.get(insumo=cuajo)
        assert mov.lote_proveedor == "CJ-2611"
        assert Auditoria.objects.filter(accion="movimiento_inventario", entidad_id=str(mov.pk)).exists()

    def test_ajuste_exige_motivo(self, admin, insumos):
        cuajo, _ = insumos
        with pytest.raises(ReglaNegocio, match="motivo"):
            inventario.salida_por_ajuste(admin, cuajo, D("10"), nota="  ")
        inventario.salida_por_ajuste(admin, cuajo, D("10"), nota="Se derramó")
        assert stock(cuajo)["stock"] == D("490")

    def test_no_se_ajusta_mas_de_lo_disponible(self, admin, insumos):
        cuajo, _ = insumos
        with pytest.raises(ReglaNegocio, match="Solo hay 500"):
            inventario.salida_por_ajuste(admin, cuajo, D("501"), nota="x")

    def test_movimientos_no_se_editan_ni_borran(self, insumos):
        mov = MovimientoInventario.objects.first()
        mov.cantidad = D("1")
        with pytest.raises(RuntimeError):
            mov.save()
        with pytest.raises(RuntimeError):
            mov.delete()
        # Ni siquiera directo en la base.
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("UPDATE movimientos_inventario SET cantidad = 1")
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("DELETE FROM movimientos_inventario")

    def test_movimiento_de_leche_sin_lote_de_origen_es_rechazado_por_la_base(self, admin):
        with pytest.raises(IntegrityError), transaction.atomic():
            MovimientoInventario.objects.create(item="leche", tipo="salida", motivo="elaboracion",
                                                cantidad=D("10"), unidad="l", usuario=admin)

    def test_operador_no_puede_ajustar_por_api(self, como, operador, insumos):
        cuajo, _ = insumos
        r = como(operador).post(f"/api/v1/insumos/{cuajo.pk}/entrada", {"cantidad": "5", "motivo": "ajuste",
                                                                        "nota": "x"}, format="json")
        assert r.status_code == 403
        r = como(operador).post(f"/api/v1/insumos/{cuajo.pk}/entrada", {"cantidad": "5"}, format="json")
        assert r.status_code == 201 and r.data["stock"] == "505.000"
        r = como(operador).post(f"/api/v1/insumos/{cuajo.pk}/salida", {"cantidad": "5", "nota": "x"}, format="json")
        assert r.status_code == 403


# --- Iniciar lote ----------------------------------------------------------------------------

@pytest.mark.django_db
class TestIniciarLote:
    def test_descuenta_leche_y_reserva_insumos(self, operador, sesion, insumos):
        cuajo, sal = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        lq = iniciar(operador, [(ll, "80")], [(cuajo, "40"), (sal, "2")])

        assert lq.estado == "borrador" and lq.codigo == "LQ-20261126-1" and lq.litros_leche == D("80")
        ll = LoteLeche.objects.get(pk=ll.pk)
        assert ll.saldo_disponible == D("20")
        assert queso.leche_disponible(ll)["total"] == D("20")
        # Reservado: no sale del stock todavía, pero no está disponible para otro lote.
        assert stock(cuajo) == {"stock": D("500"), "reservado": D("40"), "disponible": D("460")}
        assert stock(sal)["disponible"] == D("8")
        salida = MovimientoInventario.objects.get(item="leche")
        assert (salida.tipo, salida.cantidad, salida.lote_leche_id, salida.lote_queso_id) == (
            "salida", D("80"), ll.pk, lq.pk)

    def test_usa_primero_la_leche_ya_destinada_a_queso(self, operador, sesion):
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        leche.asignar_destino(operador, ll, tipo="elaboracion_queso", litros=D("60"))
        leche.asignar_destino(operador, ll, tipo="venta", litros=D("10"))
        lq = iniciar(operador, [(ll, "70")])

        destinos = DestinoLeche.objects.filter(lote=ll)
        assert sorted((d.tipo, d.litros) for d in destinos) == [
            ("elaboracion_queso", D("10")), ("elaboracion_queso", D("60")), ("venta", D("10"))]
        assert {o.litros for o in lq.origenes.all()} == {D("60"), D("10")}
        assert LoteLeche.objects.get(pk=ll.pk).saldo_disponible == D("20")

    def test_parte_un_destino_de_queso_cuando_usa_solo_una_parte(self, operador, sesion):
        sesion(operador)
        ll = lote_leche(operador, litros="100", destino="elaboracion_queso")
        lq = iniciar(operador, [(ll, "30")])
        destinos = sorted(DestinoLeche.objects.filter(lote=ll).values_list("litros", flat=True))
        assert destinos == [D("30"), D("70")]
        assert lq.origenes.get().destino.litros == D("30")
        assert queso.leche_disponible(ll)["destinado_a_queso"] == D("70")

    def test_varios_lotes_de_leche_de_origen(self, operador, sesion):
        sesion(operador)
        m = lote_leche(operador, fecha=AYER, ordene="tarde", litros="50", destino="elaboracion_queso")
        t = lote_leche(operador, litros="80")
        lq = iniciar(operador, [(m, "50"), (t, "60")])
        assert lq.litros_leche == D("110")
        assert lq.origenes.count() == 2

    def test_no_toma_mas_leche_de_la_disponible_y_no_deja_nada_a_medias(self, operador, sesion, insumos):
        cuajo, _ = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="50")
        with pytest.raises(ReglaNegocio, match="solo tiene 50 L"):
            iniciar(operador, [(ll, "60")], [(cuajo, "10")])
        assert LoteQueso.objects.count() == 0
        assert stock(cuajo)["reservado"] == 0

    def test_insumo_insuficiente_revierte_tambien_la_leche(self, operador, sesion, insumos):
        cuajo, _ = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        with pytest.raises(ReglaNegocio, match="No alcanza Cuajo"):
            iniciar(operador, [(ll, "80")], [(cuajo, "600")])
        assert LoteLeche.objects.get(pk=ll.pk).saldo_disponible == D("100")
        assert not MovimientoInventario.objects.filter(item="leche").exists()

    def test_dos_lotes_no_reservan_el_mismo_stock(self, operador, sesion, insumos):
        cuajo, _ = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="200")
        iniciar(operador, [(ll, "100")], [(cuajo, "300")])
        with pytest.raises(ReglaNegocio, match="hay 200 ml disponibles"):
            iniciar(operador, [(ll, "100")], [(cuajo, "300")])
        assert LoteQueso.objects.get().numero == 1

    def test_no_usa_leche_de_lote_cerrado_sin_destino_queso(self, operador, sesion):
        sesion(operador)
        ll = lote_leche(operador, litros="40", destino="venta")
        leche.cerrar_lote(operador, ll)
        with pytest.raises(ReglaNegocio, match="solo tiene 0 L"):
            iniciar(operador, [(ll, "10")])

    def test_leche_usada_en_queso_no_se_puede_quitar_ni_anular(self, admin, operador, sesion):
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        lq = iniciar(operador, [(ll, "100")])
        sesion(admin)
        with pytest.raises(ReglaNegocio, match=lq.codigo):
            leche.quitar_destino(admin, lq.origenes.get().destino)
        with pytest.raises(ReglaNegocio, match="ya se usó"):
            leche.anular_lote(admin, LoteLeche.objects.get(pk=ll.pk), "error")
        with pytest.raises(ReglaNegocio, match="asignados"):
            leche.editar_lote(admin, ll, {"litros": D("90")})


# --- Cerrar lote -----------------------------------------------------------------------------

@pytest.mark.django_db
class TestCerrarLote:
    @pytest.fixture
    def en_elaboracion(self, operador, sesion, insumos):
        cuajo, sal = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        return iniciar(operador, [(ll, "90")], [(cuajo, "40"), (sal, "2")])

    def test_no_se_cierra_sin_kg_obtenidos(self, operador, en_elaboracion):
        for kg in (None, ""):
            with pytest.raises(ReglaNegocio, match="sin los kg"):
                queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=kg)
        with pytest.raises(ReglaNegocio, match="mayores a cero"):
            queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("0"))
        assert LoteQueso.objects.get(pk=en_elaboracion.pk).estado == "borrador"

    def test_cierre_libera_reserva_descuenta_lo_real_y_genera_queso(self, operador, insumos, en_elaboracion):
        cuajo, sal = insumos
        lq = queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("10"), merma_kg=D("0.5"),
                               consumos=[{"insumo": cuajo, "cantidad": D("45")}, {"insumo": sal, "cantidad": D("1.5")}])
        assert lq.estado == "pendiente"
        assert lq.rendimiento_l_kg == D("9.00")  # 90 L / 10 kg
        assert lq.rendimiento_fuera_de_rango is False
        assert lq.kg_netos == D("9.5")
        assert stock(cuajo) == {"stock": D("455"), "reservado": 0, "disponible": D("455")}
        assert stock(sal) == {"stock": D("8.5"), "reservado": 0, "disponible": D("8.5")}
        assert queso._queso_en_inventario(lq) == D("9.5")
        usos = {u.insumo_id: u.cantidad_consumida for u in lq.insumos.all()}
        assert usos == {cuajo.pk: D("45"), sal.pk: D("1.5")}

    def test_sin_consumos_toma_lo_declarado(self, operador, insumos, en_elaboracion):
        cuajo, sal = insumos
        queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("10"))
        assert stock(cuajo)["stock"] == D("460") and stock(sal)["stock"] == D("8")

    def test_insumo_no_declarado_tambien_se_descuenta(self, admin, operador, insumos, en_elaboracion):
        cuajo, sal = insumos
        cloruro = Insumo.objects.create(codigo="CACL", nombre="Cloruro de calcio", unidad="ml")
        inventario.entrada(admin, cloruro, D("100"))
        lq = queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("10"),
                               consumos=[{"insumo": cuajo, "cantidad": D("40")}, {"insumo": cloruro, "cantidad": D("20")}])
        assert stock(cloruro)["stock"] == D("80")
        assert stock(sal) == {"stock": D("10"), "reservado": 0, "disponible": D("10")}  # sal no se usó
        assert lq.insumos.count() == 3

    def test_merma_no_puede_superar_lo_obtenido(self, operador, en_elaboracion):
        with pytest.raises(ReglaNegocio, match="merma"):
            queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("10"), merma_kg=D("10"))

    @override_settings(QUESO_RENDIMIENTO_MIN_L_KG=8, QUESO_RENDIMIENTO_MAX_L_KG=10)
    def test_rendimiento_fuera_de_rango_queda_marcado(self, operador, en_elaboracion):
        lq = queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("7.5"))
        assert lq.rendimiento_l_kg == D("12.00") and lq.rendimiento_fuera_de_rango is True

    def test_no_se_cierra_dos_veces(self, operador, en_elaboracion):
        queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("10"))
        with pytest.raises(ReglaNegocio, match="pendiente"):
            queso.cerrar_lote(operador, en_elaboracion, kg_obtenidos=D("11"))


# --- Aprobación ------------------------------------------------------------------------------

@pytest.mark.django_db
class TestAprobacion:
    @pytest.fixture
    def cerrado(self, operador, sesion, insumos):
        cuajo, _ = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        lq = iniciar(operador, [(ll, "100")], [(cuajo, "50")])
        return queso.cerrar_lote(operador, lq, kg_obtenidos=D("11"))

    def test_operador_no_puede_aprobar_ni_por_api(self, como, operador, cerrado):
        with pytest.raises(ReglaNegocio, match="Solo el Administrador"):
            queso.aprobar_lote(operador, cerrado)
        r = como(operador).post(f"/api/v1/lotes-queso/{cerrado.pk}/aprobar", {}, format="json")
        assert r.status_code == 403
        assert LoteQueso.objects.get(pk=cerrado.pk).estado == "pendiente"

    def test_quien_elaboro_no_aprueba_su_propio_lote_aunque_tenga_el_permiso(self, sesion, insumos):
        # Un encargado con permiso de aprobar, que no es el dueño.
        rol = Rol.objects.create(codigo="ENCARGADO", nombre="Encargado")
        rol.permisos.set(Permiso.objects.filter(codigo__startswith="queso.") | Permiso.objects.filter(
            codigo__in=["leche.ver", "leche.lote.gestionar"]))
        encargado = crear_usuario("encargado", "ENCARGADO")
        sesion(encargado)
        ll = lote_leche(encargado, litros="100")
        lq = queso.cerrar_lote(encargado, iniciar(encargado, [(ll, "100")]), kg_obtenidos=D("11"))
        with pytest.raises(ReglaNegocio, match="elaboraste vos"):
            queso.aprobar_lote(encargado, lq)

    def test_admin_aprueba_y_el_queso_queda_disponible(self, admin, sesion, cerrado):
        assert queso.resumen_inventario_queso()["kg_disponibles"] == 0
        assert queso.resumen_inventario_queso()["kg_en_revision"] == D("11")
        sesion(admin)
        lq = queso.aprobar_lote(admin, cerrado, "Buen lote")
        assert lq.estado == "aprobado" and lq.aprobado_por == admin
        assert queso.resumen_inventario_queso()["kg_disponibles"] == D("11")

    def test_rechazo_exige_comentario(self, admin, sesion, cerrado):
        sesion(admin)
        with pytest.raises(ReglaNegocio, match="comentario"):
            queso.rechazar_lote(admin, cerrado, " ")

    def test_rechazado_se_corrige_con_movimientos_de_diferencia(self, admin, operador, sesion, insumos, cerrado):
        cuajo, _ = insumos
        sesion(admin)
        queso.rechazar_lote(admin, cerrado, "Los kg no coinciden con la balanza")
        lq = LoteQueso.objects.get(pk=cerrado.pk)
        assert lq.estado == "rechazado" and lq.motivo_estado == "Los kg no coinciden con la balanza"

        sesion(operador)
        antes = MovimientoInventario.objects.count()
        lq = queso.cerrar_lote(operador, lq, kg_obtenidos=D("10.5"),
                               consumos=[{"insumo": cuajo, "cantidad": D("48")}])
        assert lq.estado == "pendiente"
        assert lq.rendimiento_l_kg == D("9.52")
        assert queso._queso_en_inventario(lq) == D("10.5")
        assert stock(cuajo)["stock"] == D("452")  # 500 - 48
        nuevos = MovimientoInventario.objects.order_by("fecha")[antes:]
        assert sorted((m.item, m.tipo, m.cantidad) for m in nuevos) == [
            ("insumo", "entrada", D("2")), ("queso", "salida", D("0.5"))]

        sesion(admin)
        queso.aprobar_lote(admin, lq)
        acciones = list(Auditoria.objects.filter(entidad="lotes_queso", entidad_id=str(lq.pk))
                        .order_by("id").values_list("accion", flat=True))
        assert acciones[0] == "crear" and "iniciar_elaboracion" in acciones
        assert [a for a in acciones if a in ("enviar", "rechazar", "aprobar")] == [
            "enviar", "rechazar", "enviar", "aprobar"]


# --- Cancelar --------------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelar:
    def test_cancelar_libera_insumos_y_la_leche_vuelve_a_estar_disponible(self, operador, sesion, insumos):
        cuajo, _ = insumos
        sesion(operador)
        ll = lote_leche(operador, litros="100")
        lq = iniciar(operador, [(ll, "100")], [(cuajo, "50")])
        with pytest.raises(ReglaNegocio, match="motivo"):
            queso.cancelar_lote(operador, lq, "")
        queso.cancelar_lote(operador, lq, "Se cortó la luz y se perdió la cuajada")
        assert LoteQueso.objects.get(pk=lq.pk).estado == "anulado"
        assert stock(cuajo) == {"stock": D("500"), "reservado": 0, "disponible": D("500")}
        assert queso.leche_disponible(LoteLeche.objects.get(pk=ll.pk))["destinado_a_queso"] == D("100")
        assert MovimientoInventario.objects.filter(item="leche", tipo="entrada", motivo="cancelacion").exists()
        otro = iniciar(operador, [(ll, "100")])
        assert otro.numero == 2

    def test_no_se_cancela_un_lote_cerrado(self, operador, sesion):
        sesion(operador)
        lq = iniciar(operador, [(lote_leche(operador), "100")])
        queso.cerrar_lote(operador, lq, kg_obtenidos=D("10"))
        with pytest.raises(ReglaNegocio, match="en elaboración"):
            queso.cancelar_lote(operador, lq, "x")


# --- Trazabilidad y API ----------------------------------------------------------------------

@pytest.mark.django_db
class TestTrazabilidadYApi:
    def test_flujo_completo_por_api(self, como, admin, operador, ventas, insumos):
        cuajo, sal = insumos
        op, ad = como(operador), como(admin)
        # Ordeñe por vaca: el lote de leche nace de las vacas.
        for caravana in ("101", "102"):
            assert op.post("/api/v1/animales", {"caravana": caravana, "nombre": f"Vaca {caravana}"},
                           format="json").status_code == 201
        vacas = {a["caravana"]: a["id"] for a in op.get("/api/v1/animales").data["results"]}
        r = op.post("/api/v1/rodeo/ordene", {"fecha": str(HOY), "ordene": "manana", "items": [
            {"animal": vacas["101"], "litros": "14.5"}, {"animal": vacas["102"], "litros": "11"}]}, format="json")
        assert r.status_code == 201, r.data
        ll = r.data["lote"]
        assert ll["litros"] == "25.5"

        disp = op.get("/api/v1/queso/leche-disponible").data
        assert [d["codigo"] for d in disp] == ["LL-20261126-M"]

        r = op.post("/api/v1/lotes-queso", {"fecha": str(HOY), "origenes": [{"lote_leche": ll["id"], "litros": "25.5"}],
                                            "insumos": [{"insumo": str(cuajo.pk), "cantidad": "12"}]}, format="json")
        assert r.status_code == 201, r.data
        lq = r.data
        r = op.post(f"/api/v1/lotes-queso/{lq['id']}/cerrar", {}, format="json")
        assert r.status_code == 409 and "kg" in r.data["detail"]
        r = op.post(f"/api/v1/lotes-queso/{lq['id']}/cerrar", {"kg_obtenidos": "3"}, format="json")
        assert r.status_code == 200 and r.data["estado"] == "pendiente" and r.data["rendimiento_l_kg"] == "8.50"
        assert ad.post(f"/api/v1/lotes-queso/{lq['id']}/rechazar", {}, format="json").status_code == 409
        r = ad.post(f"/api/v1/lotes-queso/{lq['id']}/aprobar", {"comentario": "ok"}, format="json")
        assert r.status_code == 200 and r.data["estado"] == "aprobado"

        t = op.get(f"/api/v1/lotes-queso/{lq['id']}/trazabilidad").data
        assert t["origen_leche"][0]["codigo"] == "LL-20261126-M"
        assert {v["caravana"]: v["litros"] for v in t["origen_leche"][0]["vacas"]} == {"101": D("14.5"), "102": D("11")}
        assert t["insumos"][0]["nombre"] == "Cuajo líquido" and t["insumos"][0]["consumida"] == D("12")
        assert t["insumos"][0]["lotes_proveedor_recientes"] == ["CJ-2611"]
        assert {m["item"] for m in t["movimientos"]} == {"leche", "insumo", "queso"}
        assert [h["accion"] for h in t["historial"]][-1] == "aprobar"
        assert t["clientes"] == []

        r = op.get(f"/api/v1/lotes-leche/{ll['id']}/quesos").data
        assert [q["codigo"] for q in r["lotes_queso"]] == [lq["codigo"]]

        # Ventas ve el stock de queso pero no los lotes de queso ni el rodeo.
        v = como(ventas)
        assert v.get("/api/v1/inventario/queso").data["kg_disponibles"] == D("3")
        assert v.get("/api/v1/lotes-queso").status_code == 403
        assert v.get("/api/v1/animales").status_code == 403

    def test_reintento_con_mismo_id_no_duplica(self, como, operador, sesion):
        import uuid
        sesion(operador)
        ll = lote_leche(operador)
        uid = str(uuid.uuid4())
        cuerpo = {"id": uid, "fecha": str(HOY), "origenes": [{"lote_leche": str(ll.pk), "litros": "50"}]}
        op = como(operador)
        assert op.post("/api/v1/lotes-queso", cuerpo, format="json").status_code == 201
        assert op.post("/api/v1/lotes-queso", cuerpo, format="json").status_code == 200
        assert LoteQueso.objects.count() == 1
        assert LoteLeche.objects.get(pk=ll.pk).saldo_disponible == D("50")

    def test_menu_muestra_los_modulos_de_la_fase_3(self, como, operador, ventas):
        modulos = {m["codigo"]: m for m in como(operador).get("/api/v1/auth/me").data["modulos"]}
        assert all(modulos[c]["disponible"] for c in ("rodeo", "queso", "inventario"))
        assert "rodeo" not in {m["codigo"] for m in como(ventas).get("/api/v1/auth/me").data["modulos"]}
