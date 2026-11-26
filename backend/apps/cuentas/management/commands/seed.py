"""Carga inicial: establecimiento, parámetros y tres usuarios de prueba (uno por rol).

Es idempotente: se puede correr varias veces sin duplicar nada.
Las claves de prueba se pueden cambiar con variables de entorno SEED_CLAVE_*.
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Configuracion, Establecimiento
from apps.cuentas.catalogo import ADMIN, OPERADOR, VENTAS
from apps.cuentas.models import Rol, Usuario, UsuarioRol
from apps.cuentas.servicios import sincronizar_roles_y_permisos

USUARIOS_DEMO = [
    ("admin", "Dueño (Administrador)", ADMIN, "SEED_CLAVE_ADMIN", "Tambo.Admin2026"),
    ("operador", "Tambero de prueba", OPERADOR, "SEED_CLAVE_OPERADOR", "Tambo.Operador2026"),
    ("ventas", "Vendedor de prueba", VENTAS, "SEED_CLAVE_VENTAS", "Tambo.Ventas2026"),
]

CONFIGURACION_DEMO = [
    ("moneda", "PYG", "Moneda de trabajo (Guaraníes, sin decimales)"),
    ("zona_horaria", "America/Asuncion", "Zona horaria del establecimiento"),
    ("gastos.presupuesto_mensual_temporada_baja", 2_000_000, "Gasto mensual de referencia en temporada baja (Gs.)"),
    ("gastos.presupuesto_mensual_temporada_alta", 4_000_000, "Gasto mensual de referencia en temporada alta (Gs.)"),
    ("ventas.condicion_por_defecto", "contado", "Las ventas de queso son al contado por ahora"),
    ("queso.precio_lista_kg", 40_000, "Precio de lista del queso Paraguay por kg (Gs.)"),
    ("ordene.sesiones", ["mañana", "tarde"], "Sesiones de ordeñe por día"),
]


class Command(BaseCommand):
    help = "Crea el establecimiento, parámetros iniciales y usuarios de prueba (admin, operador, ventas)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        sincronizar_roles_y_permisos()

        establecimiento, _ = Establecimiento.objects.get_or_create(
            nombre="Tambo Lechero Kuñatai",
            defaults={"direccion": "Barrio Caaguazú, Ñemby, Paraguay"},
        )
        for clave, valor, descripcion in CONFIGURACION_DEMO:
            Configuracion.objects.get_or_create(
                establecimiento=establecimiento, clave=clave,
                defaults={"valor": valor, "descripcion": descripcion},
            )

        for usuario, nombre, rol_codigo, variable, clave_defecto in USUARIOS_DEMO:
            user = Usuario.objects.filter(usuario=usuario).first()
            if user is None:
                user = Usuario.objects.create_user(
                    usuario, os.environ.get(variable, clave_defecto), nombre=nombre,
                    is_staff=(rol_codigo == ADMIN), is_superuser=(rol_codigo == ADMIN),
                )
                self.stdout.write(f"  usuario creado: {usuario}")
            UsuarioRol.objects.get_or_create(
                usuario=user, rol=Rol.objects.get(codigo=rol_codigo), establecimiento=establecimiento
            )

        self._leche_demo(establecimiento)
        self.stdout.write(self.style.SUCCESS("Seed listo."))

    def _leche_demo(self, establecimiento):
        """Historial de ordeñe de los últimos 20 días (sin hoy), solo si todavía no hay lotes.
        Ayer queda bajo, para que se vea la alerta del panel."""
        import datetime
        import random
        from decimal import Decimal

        from django.utils import timezone

        from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
        from apps.leche import servicios
        from apps.leche.models import LoteLeche

        if LoteLeche.objects.exists():
            return
        operador = Usuario.objects.get(usuario="operador")
        token = iniciar_contexto()
        fijar_usuario(operador)
        try:
            azar = random.Random(42)
            hoy = timezone.localdate()
            for dias_atras in range(20, 0, -1):
                fecha = hoy - datetime.timedelta(days=dias_atras)
                for ordene, base in (("manana", 150), ("tarde", 125)):
                    litros = Decimal(base + azar.randint(-12, 12))
                    if dias_atras == 1:
                        litros = Decimal(base - 45)
                    lote, _ = servicios.crear_lote(
                        operador, fecha=fecha, ordene=ordene, litros=litros, establecimiento=establecimiento,
                        temperatura_c=Decimal("4.0") if ordene == "manana" else None,
                    )
                    venta = Decimal(azar.choice([0, 10, 15, 20]))
                    if venta:
                        servicios.asignar_destino(operador, lote, tipo="venta", litros=venta)
                    if dias_atras > 1:
                        servicios.asignar_destino(operador, lote, tipo="elaboracion_queso", litros=litros - venta)
                        servicios.cerrar_lote(operador, lote)
            self.stdout.write("  historial de leche de demo: 20 días")
        finally:
            terminar_contexto(token)
