"""Puesta en marcha en producción: crea el establecimiento y el primer Administrador (sin datos de prueba).

    docker compose -f docker-compose.prod.yml exec backend python manage.py iniciar

Pregunta lo que falta. La clave no se muestra al escribirla y tiene que cumplir las reglas de claves.
Se corre una sola vez; los demás usuarios se crean después desde la pantalla Usuarios y roles.
"""
import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import auditoria
from apps.core.models import Configuracion, Establecimiento
from apps.cuentas.catalogo import ADMIN
from apps.cuentas.models import Rol, Usuario, UsuarioRol
from apps.cuentas.servicios import sincronizar_roles_y_permisos

from .seed import CONFIGURACION_DEMO


class Command(BaseCommand):
    help = "Crea el establecimiento y el primer usuario Administrador para empezar a usar el sistema."

    def add_arguments(self, parser):
        parser.add_argument("--establecimiento", help="Nombre del tambo")
        parser.add_argument("--direccion", default="")
        parser.add_argument("--usuario", help="Usuario para entrar (p. ej. el nombre del dueño, en minúsculas)")
        parser.add_argument("--nombre", help="Nombre completo del Administrador")
        parser.add_argument("--clave-desde", metavar="VARIABLE",
                            help="Tomar la clave de esta variable de entorno en lugar de preguntarla")

    def _pedir(self, valor, pregunta):
        while not (valor or "").strip():
            valor = input(f"{pregunta}: ")
        return valor.strip()

    def handle(self, *args, **o):
        if Usuario.objects.filter(roles__codigo=ADMIN, is_active=True).exists():
            raise CommandError("Ya hay un Administrador activo. Los demás usuarios se crean desde la pantalla "
                               "Usuarios y roles.")
        nombre_tambo = self._pedir(o["establecimiento"], "Nombre del tambo")
        usuario = self._pedir(o["usuario"], "Usuario del Administrador (para entrar)").lower()
        nombre = self._pedir(o["nombre"], "Nombre completo del Administrador")
        if Usuario.objects.filter(usuario=usuario).exists():
            raise CommandError(f"Ya existe el usuario {usuario}.")

        if o["clave_desde"]:
            clave = os.environ.get(o["clave_desde"], "")
            if not clave:
                raise CommandError(f"La variable {o['clave_desde']} está vacía.")
        else:
            clave = getpass.getpass("Clave (no se ve al escribir): ")
            if clave != getpass.getpass("Repetí la clave: "):
                raise CommandError("Las claves no coinciden. No se creó nada.")
        try:
            validate_password(clave, Usuario(usuario=usuario, nombre=nombre))
        except ValidationError as e:
            raise CommandError("La clave no sirve: " + " ".join(e.messages))

        with transaction.atomic():
            sincronizar_roles_y_permisos()
            establecimiento = Establecimiento.objects.first() or Establecimiento.objects.create(
                nombre=nombre_tambo, direccion=o["direccion"])
            for clave_conf, valor, descripcion in CONFIGURACION_DEMO:
                Configuracion.objects.get_or_create(establecimiento=establecimiento, clave=clave_conf,
                                                    defaults={"valor": valor, "descripcion": descripcion})
            admin = Usuario.objects.create_user(usuario, clave, nombre=nombre, is_staff=True, is_superuser=True)
            UsuarioRol.objects.create(usuario=admin, rol=Rol.objects.get(codigo=ADMIN), establecimiento=establecimiento)
            auditoria.registrar("crear", "usuarios", admin.pk, usuario=None,
                                cambios={"usuario": usuario, "rol": ADMIN}, motivo="Puesta en marcha (manage.py iniciar)")
        self.stdout.write(self.style.SUCCESS(
            f"Listo: «{establecimiento.nombre}» con el Administrador {usuario}. Entrá al sistema con ese usuario, "
            "cargá los precios (Ventas → Precios), los insumos y los usuarios del equipo."))
