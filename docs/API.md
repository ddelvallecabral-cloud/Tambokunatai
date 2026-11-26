# API del ERP Tambo Kuñatai

Todas las rutas van bajo `/api/v1` y, salvo `salud` y las de `auth`, piden sesión (token `Bearer`).
Los errores siempre vuelven en JSON con un campo `detail` en castellano pensado para mostrarle al usuario;
los de validación traen además un mensaje por campo. Códigos: 400 datos mal cargados, 401 sin sesión,
403 sin permiso, 404 no existe, 409 choca con una regla del negocio (por ejemplo, un lote ya cerrado),
429 demasiados intentos, 500 falla del servidor.

## Autenticación, usuarios y auditoría

Todas bajo `/api/v1`.

| Método       | Ruta                    | Quién                        | Para qué                                        |
| ------------ | ----------------------- | ---------------------------- | ----------------------------------------------- |
| POST         | `/auth/login`           | Público                      | Usuario y clave → token de acceso + cookie      |
| POST         | `/auth/refresh`         | Con cookie                   | Nuevo token de acceso (rota la cookie)          |
| POST         | `/auth/logout`          | Con cookie                   | Cierra la sesión e invalida la cookie           |
| GET          | `/auth/me`              | Autenticado                  | Perfil, roles, permisos y módulos del menú      |
| POST         | `/auth/cambiar-clave`   | Autenticado                  | Cambio de clave propia                          |
| GET          | `/usuarios`             | `usuarios.ver` (Admin)       | Listar usuarios                                 |
| POST         | `/usuarios`             | `usuarios.gestionar` (Admin) | Registrar usuario con roles                     |
| PATCH        | `/usuarios/{id}`        | `usuarios.gestionar` (Admin) | Editar, cambiar roles, desactivar, nueva clave  |
| GET          | `/roles`                | `usuarios.ver` (Admin)       | Roles con sus permisos                          |
| GET          | `/auditoria`            | `auditoria.ver` (Admin)      | Consultar auditoría (filtros: accion, entidad, usuario, desde, hasta) |
| GET          | `/auditoria/verificar`  | `auditoria.ver` (Admin)      | Verifica que nadie alteró la auditoría          |
| GET          | `/salud`                | Público                      | Chequeo de que el sistema responde              |

## Leche

| Método | Ruta | Quién | Para qué |
| ------ | ---- | ----- | -------- |
| GET    | `/lotes-leche` | Operador, Admin | Listado. Filtros: `fecha`, `desde`, `hasta`, `ordene`, `destino` (`pendiente` = con saldo), `estado` |
| POST   | `/lotes-leche` | Operador, Admin | Registrar lote (`fecha`, `ordene`, `litros`, calidad opcional, `destino`) |
| GET    | `/lotes-leche/{id}` | Operador, Admin | Detalle con destinos y saldo |
| PATCH  | `/lotes-leche/{id}` | Operador, Admin | Corregir. Operador en día anterior → queda pendiente; Admin en cerrado → requiere `motivo` |
| POST   | `/lotes-leche/{id}/destinos` | Operador, Admin | Asignar litros a un destino (`tipo`, `litros`) |
| DELETE | `/lotes-leche/{id}/destinos/{destino}` | Operador (hoy), Admin | Quitar una asignación |
| POST   | `/lotes-leche/{id}/cerrar` | Operador, Admin | Cerrar (exige saldo 0) |
| POST   | `/lotes-leche/{id}/aprobar` · `/rechazar` | Admin | Decidir una corrección pendiente |
| POST   | `/lotes-leche/{id}/reabrir` · `/anular` | Admin | Con `motivo` |
| GET    | `/lotes-leche/resumen?fecha=` | Operador, Admin | Litros del día por ordeñe y por destino |
| GET    | `/leche/tablero` | Operador, Admin | Hoy, mes, últimos 14 días, alertas, correcciones pendientes |

## Rodeo, inventario y queso

| Método | Ruta | Quién | Para qué |
| ------ | ---- | ----- | -------- |
| GET/POST | `/animales` | Operador, Admin | Plantel (con promedio 7 días y tendencia) y alta |
| PATCH  | `/animales/{id}` | Operador, Admin | Editar (situación, nombre, raza) |
| GET    | `/animales/{id}/produccion?dias=30` | Operador, Admin | Serie diaria mañana/tarde |
| GET    | `/rodeo/ordene?fecha=&ordene=` | Operador, Admin | Planilla de la sesión |
| POST   | `/rodeo/ordene` | Operador, Admin | Guardar planilla completa (`fecha`, `ordene`, `items`, `destino`) |
| GET/POST | `/insumos` | Todos ven · Admin crea | Insumos con `stock`, `reservado`, `disponible`, `bajo_minimo` |
| POST   | `/insumos/{id}/entrada` | Operador (compra), Admin (ajuste) | Entrada con `lote_proveedor` |
| POST   | `/insumos/{id}/salida` | Admin | Ajuste con `nota` obligatoria |
| GET    | `/movimientos-inventario` | Todos | Filtros: `item`, `tipo`, `insumo`, `lote_leche`, `lote_queso`, `desde`, `hasta` |
| GET    | `/inventario/leche` · `/inventario/queso` | Todos | Leche disponible para queso; queso por lote |
| GET/POST | `/lotes-queso` | Operador, Admin | Listado (filtros `estado`, `desde`, `hasta`, `fuera_de_rango`) e inicio |
| POST   | `/lotes-queso/{id}/cerrar` | Operador, Admin | `kg_obtenidos` (obligatorio), `merma_kg`, `consumos` |
| POST   | `/lotes-queso/{id}/aprobar` · `/rechazar` | Admin | `comentario` (obligatorio al rechazar) |
| POST   | `/lotes-queso/{id}/cancelar` | Quien lo inició, Admin | `motivo` |
| GET    | `/lotes-queso/{id}/trazabilidad` | Operador, Admin | Cadena completa del lote |
| GET    | `/lotes-leche/{id}/quesos` | Operador, Admin | En qué quesos terminó un lote de leche |
| GET    | `/queso/leche-disponible` · `/queso/resumen` | Operador, Admin | Para el asistente y el panel |

## Ventas y cuentas por cobrar

| Método | Ruta | Quién | Para qué |
| ------ | ---- | ----- | -------- |
| GET/POST/PATCH | `/clientes` | Todos ven · Ventas y Admin editan | Filtros `buscar`, `tipo`, `activo`; con `saldo_pendiente` y `ultima_compra` |
| GET    | `/clientes/{id}/historial` | Todos | Totales, lotes recibidos y compras |
| GET/POST/PATCH | `/precios` | Todos ven · Admin edita | Tabla de precios (base, por tipo de cliente, por volumen) |
| GET    | `/precios/cotizar?cliente=&producto=&cantidad=` | Todos | Precio, total, stock y lotes disponibles |
| GET/POST | `/ventas` | Todos ven · Ventas y Admin registran | Filtros `desde`, `hasta`, `cliente`, `producto`, `estado_venta`, `lote_queso`, `buscar` |
| POST   | `/ventas/{id}/entregar` · `/cobrar` | Ventas, Admin | Entrega; cobro con `monto`, `medio`, `referencia` |
| POST   | `/ventas/{id}/anular` | Admin | `motivo` (devuelve el stock) |
| GET    | `/cuentas-por-cobrar` · `/cuentas-por-cobrar-resumen` | Admin | Cuentas (`estado`, `cliente`, `vencidas=1`) y resumen financiero |
| POST   | `/cuentas-por-cobrar/cobros/{id}/anular` | Admin | `motivo` |

## Proveedores, compras y gastos

| Método | Ruta | Quién | Para qué |
| ------ | ---- | ----- | -------- |
| GET/POST/PATCH | `/proveedores` | Todos con Compras ven · Operador y Admin editan | Filtros `buscar`, `tipo`, `activo`; con `saldo_pendiente` y `ultima_compra` |
| GET/POST | `/compras` | Operador y Admin | Registra y confirma (stock + cuenta por pagar). Filtros `desde`, `hasta`, `proveedor`, `insumo`, `estado_compra` |
| GET/POST | `/compras/{id}/comprobante` | Operador y Admin | Ver o subir la foto/PDF de la factura (multipart, campo `comprobante`) |
| POST   | `/compras/{id}/pagar` · `/anular` | Admin | Pago (`monto`, `medio`, `referencia`); anulación con `motivo` |
| GET    | `/cuentas-por-pagar` · `/cuentas-por-pagar-resumen` | Admin | Cuentas (`estado`, `proveedor`, `vencidas=1`) y resumen |
| POST   | `/cuentas-por-pagar/pagos/{id}/anular` | Admin | `motivo` |
| GET/POST | `/gastos` | Quien tenga Gastos (cada uno ve los suyos; Admin todos) | Alta multipart con foto. Filtros `categoria`, `centro_costo`, `estado`, `desde`, `hasta` |
| GET    | `/gastos/resumen` | Igual | Totales, pendientes, por categoría y centro, y el monto que pide aprobación |
| POST   | `/gastos/{id}/corregir` | Quien lo cargó | Corregir un gasto pendiente o rechazado y reenviarlo |
| GET    | `/gastos/{id}/comprobante` | Quien lo ve | Foto o PDF |
| POST   | `/gastos/{id}/aprobar` · `/rechazar` · `/anular` | Admin | `comentario` (obligatorio al rechazar) o `motivo` |
| GET    | `/aprobaciones/pendientes` | Admin | Cuántos gastos, lotes de queso y correcciones de leche esperan |

## Tablero, reportes, control y alertas

Los períodos van como `desde` y `hasta` (AAAA-MM-DD); si faltan, es el mes en curso.

| Método | Ruta | Quién | Para qué |
| ------ | ---- | ----- | -------- |
| GET | `/tablero` | Quien vea reportes operativos o financieros | Producción y alertas; `financiero` solo para el Admin; `pendientes` para quien aprueba |
| GET | `/reportes/estado-resultados` | Admin | Ingresos por producto, gastos por categoría y centro, compras de insumos y resultado |
| GET | `/reportes/flujo-caja?agrupar=dia\|mes` | Admin | Cobros, pagos a proveedores, gastos, neto y acumulado |
| GET | `/reportes/rentabilidad-lotes` · `/reportes/rentabilidad-productos` | Admin | Costo y resultado por lote de queso; margen por producto |
| GET | `/reportes/mis-ventas` | Ventas (y Admin) | Lo que vendió y cobró quien consulta, y lo que le falta cobrar |
| GET | `/reportes/aprobaciones` | Admin | Quién aprobó o rechazó qué y cuándo (`entidad`, `usuario`) |
| GET | `/reportes/{reporte}.pdf` · `.xlsx` | Igual que el reporte | `estado-resultados`, `flujo-caja`, `flujo-caja-mensual`, `rentabilidad-lotes`, `rentabilidad-productos`, `aprobaciones` |
| GET | `/control/registros-editados?sin_revisar=1` | Admin | Ediciones de registros cerrados, reaperturas y anulaciones |
| POST | `/control/registros-editados/{id}/revisar` | Admin | Marcar como revisado (`nota`) |
| GET | `/alertas` | Operador y Admin | Alertas vigentes (el Operador no ve las de cuentas) |
| GET/PUT | `/alertas/configuracion` | Ver: Operador y Admin · Cambiar: Admin | Umbrales de cada alerta y si está activa |

## Para programadores: permisos y auditoría en código nuevo

**Restringir un endpoint por permiso o rol** (`apps/cuentas/permisos.py`):

```python
from apps.cuentas.permisos import requiere_permiso, requiere_rol

class LoteQuesoViewSet(viewsets.ModelViewSet):
    permission_classes = [requiere_permiso("queso.ver")]

    @action(detail=True, methods=["post"], permission_classes=[requiere_permiso("queso.lote.aprobar")])
    def aprobar(self, request, pk=None):
        lote = self.get_object()
        lote.aprobar()
        return Response(...)
```

**Hacer auditable una entidad** (`apps/core/mixins.py`):

```python
from apps.core.mixins import AuditableModel

class LoteQueso(AuditableModel):
    kg_obtenidos = models.DecimalField(...)
```

Con eso la entidad tiene `creado_por`, `fecha_creacion`, `modificado_por`, `fecha_modificacion`,
`estado`, `aprobado_por`, `fecha_aprobacion` y `version`, completados solos con el usuario de la
petición; cada alta, edición y cambio de estado queda en `auditoria`; y un registro aprobado o
cerrado no se puede editar hasta que el Administrador lo reabra con motivo.

**Agregar un permiso o cambiar un rol**: se edita `apps/cuentas/catalogo.py` y se corre `migrate`.
