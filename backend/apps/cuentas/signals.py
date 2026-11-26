from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def sincronizar_catalogo(sender, app_config=None, **kwargs):
    if app_config is None or app_config.name != "apps.cuentas":
        return
    from .servicios import sincronizar_roles_y_permisos

    sincronizar_roles_y_permisos()
