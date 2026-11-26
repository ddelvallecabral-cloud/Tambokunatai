import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError

from apps.core import auditoria
from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
from apps.core.mixins import RegistroBloqueado, TransicionInvalida
from apps.core.models import Auditoria
from tests.app_prueba.models import Documento


@pytest.fixture
def sesion_de():
    """Simula una petición autenticada para que el mixin tome el usuario del contexto."""
    tokens = []

    def _sesion(usuario):
        tokens.append(iniciar_contexto(ip="10.0.0.5", dispositivo="pytest"))
        fijar_usuario(usuario)

    yield _sesion
    for t in reversed(tokens):
        terminar_contexto(t)


@pytest.mark.django_db
class TestAuditableModel:
    def test_alta_completa_creado_por_y_audita(self, operador, sesion_de):
        sesion_de(operador)
        doc = Documento.objects.create(titulo="Lote 1", monto=100)
        assert doc.creado_por == operador
        assert doc.fecha_creacion is not None
        assert doc.estado == "borrador"
        fila = Auditoria.objects.get(accion="crear", entidad="prueba_documento")
        assert fila.usuario == operador and fila.ip == "10.0.0.5"

    def test_edicion_guarda_solo_lo_que_cambio(self, operador, sesion_de):
        sesion_de(operador)
        doc = Documento.objects.create(titulo="Lote 1", monto=100)
        doc.monto = 150
        doc.save()
        doc.refresh_from_db()
        assert doc.modificado_por == operador
        assert doc.version == 2
        fila = Auditoria.objects.get(accion="editar")
        assert fila.cambios == {"monto": [100, 150]}

    def test_flujo_de_aprobacion(self, operador, admin, sesion_de):
        sesion_de(operador)
        doc = Documento.objects.create(titulo="Gasto", monto=3_000_000)
        doc.enviar()
        sesion_de(admin)
        doc.aprobar()
        doc.refresh_from_db()
        assert doc.estado == "aprobado"
        assert doc.aprobado_por == admin and doc.fecha_aprobacion
        acciones = list(Auditoria.objects.filter(entidad="prueba_documento").order_by("id").values_list("accion", flat=True))
        assert acciones == ["crear", "enviar", "aprobar"]
        assert Auditoria.objects.get(accion="aprobar").snapshot["monto"] == 3_000_000

    def test_registro_aprobado_no_se_puede_editar(self, operador, admin, sesion_de):
        sesion_de(operador)
        doc = Documento.objects.create(titulo="Lote", monto=1)
        doc.enviar()
        sesion_de(admin)
        doc.aprobar()
        doc.monto = 999
        with pytest.raises(RegistroBloqueado):
            doc.save()

    def test_reabrir_exige_motivo_y_desbloquea(self, operador, admin, sesion_de):
        sesion_de(admin)
        doc = Documento.objects.create(titulo="Lote", monto=1)
        doc.enviar()
        doc.aprobar()
        with pytest.raises(TransicionInvalida):
            doc.reabrir("")
        doc.reabrir("Se cargaron mal los kg")
        assert doc.estado == "borrador" and doc.aprobado_por is None
        doc.monto = 2
        doc.save()
        assert Auditoria.objects.get(accion="reabrir").motivo == "Se cargaron mal los kg"

    def test_transicion_invalida(self, admin, sesion_de):
        sesion_de(admin)
        doc = Documento.objects.create(titulo="x")
        with pytest.raises(TransicionInvalida):
            doc.aprobar()


@pytest.mark.django_db
class TestInmutabilidad:
    def test_la_base_rechaza_update_directo(self, admin):
        auditoria.registrar("login", "usuarios", admin.pk, usuario=admin)
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as c:
                c.execute("UPDATE auditoria SET accion = 'nada'")

    def test_la_base_rechaza_delete_directo(self, admin):
        auditoria.registrar("login", "usuarios", admin.pk, usuario=admin)
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as c:
                c.execute("DELETE FROM auditoria")

    def test_el_modelo_no_permite_modificar(self, admin):
        fila = auditoria.registrar("login", "usuarios", admin.pk, usuario=admin)
        with pytest.raises(RuntimeError):
            fila.save()

    def test_cadena_de_hashes_integra(self, admin):
        for _ in range(3):
            auditoria.registrar("login", "usuarios", admin.pk, usuario=admin)
        filas = list(Auditoria.objects.order_by("id"))
        assert filas[1].hash_anterior == filas[0].hash
        assert auditoria.verificar_cadena()["integra"]

    def test_cadena_detecta_alteracion(self, admin):
        for _ in range(3):
            auditoria.registrar("login", "usuarios", admin.pk, usuario=admin)
        segunda = Auditoria.objects.order_by("id")[1]
        with connection.cursor() as c:  # simula a alguien que desactiva el trigger y edita a mano
            c.execute("SET CONSTRAINTS ALL IMMEDIATE")
            c.execute("ALTER TABLE auditoria DISABLE TRIGGER auditoria_sin_cambios")
            c.execute("UPDATE auditoria SET accion = 'editar' WHERE id = %s", [segunda.id])
            c.execute("ALTER TABLE auditoria ENABLE TRIGGER auditoria_sin_cambios")
        resultado = auditoria.verificar_cadena()
        assert not resultado["integra"] and resultado["primera_fila_alterada"] == segunda.id

    def test_endpoint_verificar(self, como, admin):
        r = como(admin).get("/api/v1/auditoria/verificar")
        assert r.status_code == 200 and r.data["integra"]
