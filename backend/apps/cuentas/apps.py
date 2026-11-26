from django.apps import AppConfig


class CuentasConfig(AppConfig):
    name = "apps.cuentas"
    verbose_name = "Usuarios y permisos"

    def ready(self):
        from . import signals  # noqa: F401
