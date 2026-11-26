import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Espera hasta que la base de datos acepte conexiones (máximo 60 segundos)."

    def handle(self, *args, **opciones):
        for _ in range(60):
            try:
                connection.ensure_connection()
                return
            except OperationalError:
                time.sleep(1)
        raise CommandError("La base de datos no respondió en 60 segundos.")
