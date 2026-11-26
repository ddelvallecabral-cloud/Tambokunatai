from django.db import transaction

from .catalogo import MODULOS, PERMISOS, ROLES


@transaction.atomic
def sincronizar_roles_y_permisos():
    """Deja las tablas de permisos y roles base iguales al catálogo del código."""
    from .models import Permiso, Rol

    por_codigo = {}
    for codigo, modulo, descripcion in PERMISOS:
        permiso, _ = Permiso.objects.update_or_create(
            codigo=codigo, defaults={"modulo": modulo, "descripcion": descripcion}
        )
        por_codigo[codigo] = permiso

    for codigo, datos in ROLES.items():
        rol, _ = Rol.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": datos["nombre"], "descripcion": datos["descripcion"], "es_sistema": True},
        )
        rol.permisos.set([por_codigo[c] for c in datos["permisos"]])


def modulos_de(usuario) -> list[dict]:
    """Módulos del menú que el usuario puede ver, en orden."""
    permisos = usuario.permisos_codigos()
    return [
        {k: m[k] for k in ("codigo", "nombre", "ruta", "disponible", "fase")}
        for m in MODULOS
        if m["permiso"] is None or m["permiso"] in permisos
    ]
