"""Catálogo de permisos, roles base y módulos del menú.

Es la única fuente de verdad: al correr `migrate` se sincroniza con las tablas
`permisos`, `roles` y `rol_permisos` (ver signals.py). Para agregar un permiso o
cambiar qué incluye un rol base, se edita este archivo y se vuelve a migrar.
"""

ADMIN = "ADMIN"
OPERADOR = "OPERADOR"
VENTAS = "VENTAS"

# (código, módulo, descripción). Formato del código: modulo.entidad.accion
PERMISOS = [
    # Administración del sistema
    ("usuarios.ver", "administracion", "Ver usuarios y roles"),
    ("usuarios.gestionar", "administracion", "Crear, editar y desactivar usuarios; asignar roles"),
    ("configuracion.gestionar", "administracion", "Editar umbrales y parámetros"),
    ("auditoria.ver", "auditoria", "Consultar el registro de auditoría"),
    ("registros.reabrir", "administracion", "Reabrir registros aprobados o cerrados"),
    ("registros.anular", "administracion", "Anular cualquier registro"),
    # Rodeo y ordeñe
    ("rodeo.ver", "rodeo", "Ver plantel, ordeñe y sanidad"),
    ("rodeo.animal.gestionar", "rodeo", "Alta y edición de animales"),
    ("rodeo.ordene.registrar", "rodeo", "Registrar ordeñe por vaca y sesión"),
    ("rodeo.tratamiento.registrar", "rodeo", "Registrar tratamientos y carencias"),
    # Leche
    ("leche.ver", "leche", "Ver lotes de leche"),
    ("leche.lote.gestionar", "leche", "Crear lotes y asignar destinos"),
    ("leche.lote.cerrar", "leche", "Cerrar lotes de leche"),
    ("leche.lote.aprobar", "leche", "Aprobar correcciones, editar lotes cerrados y anular"),
    # Queso
    ("queso.ver", "queso", "Ver lotes de queso"),
    ("queso.lote.gestionar", "queso", "Crear y editar lotes de queso en borrador"),
    ("queso.lote.enviar", "queso", "Enviar lote de queso a aprobación"),
    ("queso.lote.aprobar", "queso", "Aprobar o rechazar lotes de queso"),
    ("queso.receta.gestionar", "queso", "Editar recetas y rendimientos"),
    # Inventario
    ("inventario.ver", "inventario", "Ver stock"),
    ("inventario.ver_costos", "inventario", "Ver costos unitarios"),
    ("inventario.ajuste.proponer", "inventario", "Proponer ajustes de inventario"),
    ("inventario.ajuste.aprobar", "inventario", "Aprobar ajustes de inventario"),
    ("inventario.catalogo.gestionar", "inventario", "Editar productos, insumos y depósitos"),
    # Ventas
    ("ventas.ver", "ventas", "Ver ventas y clientes"),
    ("ventas.cliente.gestionar", "ventas", "Crear y editar clientes"),
    ("ventas.venta.registrar", "ventas", "Registrar, confirmar y entregar ventas"),
    ("ventas.venta.aprobar", "ventas", "Aprobar ventas fuera de límite"),
    ("ventas.cobro.registrar", "ventas", "Registrar cobros"),
    # Compras
    ("compras.ver", "compras", "Ver compras y proveedores"),
    ("compras.compra.registrar", "compras", "Cargar compras y proveedores"),
    ("compras.compra.aprobar", "compras", "Aprobar compras"),
    # Gastos
    ("gastos.ver", "gastos", "Ver gastos propios"),
    ("gastos.ver_todos", "gastos", "Ver gastos de todos"),
    ("gastos.gasto.registrar", "gastos", "Cargar gastos"),
    ("gastos.gasto.aprobar", "gastos", "Aprobar gastos y cerrar el mes"),
    # Reportes
    ("reportes.ver", "reportes", "Entrar al módulo de reportes"),
    ("reportes.operativos", "reportes", "Producción y rendimiento"),
    ("reportes.ventas_propias", "reportes", "Reportes de ventas propias"),
    ("reportes.ventas_todas", "reportes", "Reportes de ventas de todos"),
    ("reportes.financieros", "reportes", "Costos, resultados, flujo de caja y cuentas por cobrar"),
]

CODIGOS_PERMISOS = {p[0] for p in PERMISOS}

ROLES = {
    ADMIN: {
        "nombre": "Administrador",
        "descripcion": "Dueño. Aprueba, reabre, anula y ve las finanzas globales.",
        "permisos": sorted(CODIGOS_PERMISOS),
    },
    OPERADOR: {
        "nombre": "Operador",
        "descripcion": "Tamberos y encargados de elaboración.",
        "permisos": [
            "rodeo.ver", "rodeo.animal.gestionar", "rodeo.ordene.registrar", "rodeo.tratamiento.registrar",
            "leche.ver", "leche.lote.gestionar", "leche.lote.cerrar",
            "queso.ver", "queso.lote.gestionar", "queso.lote.enviar",
            "inventario.ver", "inventario.ajuste.proponer",
            "compras.ver", "compras.compra.registrar",
            "gastos.ver", "gastos.gasto.registrar",
            "reportes.ver", "reportes.operativos",
        ],
    },
    VENTAS: {
        "nombre": "Ventas",
        "descripcion": "Toma pedidos, entrega y cobra.",
        "permisos": [
            "ventas.ver", "ventas.cliente.gestionar", "ventas.venta.registrar", "ventas.cobro.registrar",
            "inventario.ver",
            "gastos.ver", "gastos.gasto.registrar",
            "reportes.ver", "reportes.ventas_propias",
        ],
    },
}

# Menú lateral. Un usuario ve un módulo solo si tiene su permiso; `disponible` indica
# si ya está construido (los que no, se muestran en gris).
MODULOS = [
    {"codigo": "inicio", "nombre": "Inicio", "ruta": "/", "permiso": None, "disponible": True, "fase": 1},
    {"codigo": "rodeo", "nombre": "Rodeo", "ruta": "/rodeo", "permiso": "rodeo.ver", "disponible": False, "fase": 3},
    {"codigo": "leche", "nombre": "Leche", "ruta": "/leche", "permiso": "leche.ver", "disponible": True, "fase": 2},
    {"codigo": "queso", "nombre": "Queso", "ruta": "/queso", "permiso": "queso.ver", "disponible": False, "fase": 3},
    {"codigo": "inventario", "nombre": "Inventario", "ruta": "/inventario", "permiso": "inventario.ver", "disponible": False, "fase": 3},
    {"codigo": "compras", "nombre": "Compras", "ruta": "/compras", "permiso": "compras.ver", "disponible": False, "fase": 3},
    {"codigo": "ventas", "nombre": "Ventas y cobros", "ruta": "/ventas", "permiso": "ventas.ver", "disponible": False, "fase": 4},
    {"codigo": "gastos", "nombre": "Gastos", "ruta": "/gastos", "permiso": "gastos.ver", "disponible": False, "fase": 5},
    {"codigo": "aprobaciones", "nombre": "Aprobaciones", "ruta": "/aprobaciones", "permiso": "gastos.gasto.aprobar", "disponible": False, "fase": 5},
    {"codigo": "reportes", "nombre": "Reportes", "ruta": "/reportes", "permiso": "reportes.ver", "disponible": False, "fase": 6},
    {"codigo": "auditoria", "nombre": "Auditoría", "ruta": "/auditoria", "permiso": "auditoria.ver", "disponible": False, "fase": 6},
    {"codigo": "usuarios", "nombre": "Usuarios y roles", "ruta": "/usuarios", "permiso": "usuarios.ver", "disponible": False, "fase": 3},
]


def _validar():
    for rol, datos in ROLES.items():
        desconocidos = set(datos["permisos"]) - CODIGOS_PERMISOS
        assert not desconocidos, f"Rol {rol} usa permisos inexistentes: {desconocidos}"
    for m in MODULOS:
        assert m["permiso"] is None or m["permiso"] in CODIGOS_PERMISOS, m


_validar()
