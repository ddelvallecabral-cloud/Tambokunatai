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

        self.stdout.write(self.style.SUCCESS("Seed listo."))
