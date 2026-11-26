# ERP Tambo Kuñatai

Sistema de gestión del tambo: ordeñe, leche, queso paraguayo, inventario, ventas, compras y gastos,
con el dueño como órgano de control y aprobación.

**Estado: Fase 4 — ventas, clientes y cuentas por cobrar.** Fase 1 (base, login, roles, auditoría),
Fase 2 (registro diario de leche, destinos, correcciones con aprobación, panel y alertas), Fase 3
(rodeo y ordeñe por vaca, insumos e inventario, elaboración de queso con aprobación y trazabilidad) y
Fase 4 (clientes, tabla de precios, ventas que descuentan inventario, cuentas por cobrar y cobros) terminadas.
Plan y decisiones en [DESIGN.md](DESIGN.md).

## Probarlo sin instalar nada (GitHub Codespaces)

1. Con tu cuenta de GitHub abierta, entrá a
   **<https://codespaces.new/ddelvallecabral-cloud/Tambokunatai?quickstart=1>** y tocá **Create codespace**.
2. Esperá unos 5 minutos la primera vez: se arma solo (base de datos, sistema y datos de prueba).
3. Se abre una pestaña con la pantalla de login. Si no se abre, en la parte de abajo del editor andá a
   **Ports** y tocá el globo al lado de **ERP Tambo (3000)**.
4. Entrá con `admin` / `Tambo.Admin2026` (o `operador`, `ventas`; ver la tabla de abajo).

Para abrirlo desde el celular: en **Ports**, clic derecho sobre el puerto 3000 → **Port Visibility → Public**
y abrí esa dirección en el teléfono. Cuando termines, cerrá la pestaña: el codespace se apaga solo a los
30 minutos sin uso. La cuenta gratuita de GitHub incluye horas de uso por mes de sobra para probar.
Para retomarlo más tarde: <https://github.com/codespaces>.

## Cómo levantarlo (Docker)

Requisitos: Docker Desktop (o Docker Engine + Compose).

```bash
cp .env.example .env        # editá SECRET_KEY antes de usarlo en serio
docker compose up --build
```

Abrí <http://localhost:3000> e ingresá con cualquiera de los usuarios de prueba:

| Usuario    | Clave                | Rol           | Ve en el menú                                              |
| ---------- | -------------------- | ------------- | ---------------------------------------------------------- |
| `admin`    | `Tambo.Admin2026`    | Administrador | Los 12 módulos, incluidos Aprobaciones, Auditoría y Usuarios |
| `operador` | `Tambo.Operador2026` | Operador      | Rodeo, Leche, Queso, Inventario, Compras, Gastos, Reportes  |
| `ventas`   | `Tambo.Ventas2026`   | Ventas        | Inventario, Ventas y cobros, Gastos, Reportes               |

Las claves se cambian en `.env` (`SEED_CLAVE_*`) antes del primer arranque.
El seed también carga datos de ejemplo: 12 animales, 20 días de ordeñe por vaca (ayer queda bajo, para que
se vea la alerta; la 105 viene bajando y la 108 subiendo), 5 insumos con stock y 6 lotes de queso
(5 aprobados y 1 pendiente con rendimiento fuera de rango).
Con `SEED_DEMO=0` no se crean usuarios de prueba.

Otros accesos:

- API: <http://localhost:8000/api/v1/> (ver lista abajo)
- Panel de respaldo de Django: <http://localhost:8000/admin/> (usuario `admin`)

Para borrar todo y empezar de cero: `docker compose down -v`.

## Cómo probar la Fase 2 (leche)

1. **Registro desde el celular.** Entrá como `operador` desde el teléfono (misma red: `http://IP-de-la-PC:3000`)
   o con el navegador en modo celular. Andá a **Leche → Registrar**: la fecha ya es hoy y el ordeñe se
   elige solo por la hora. Escribí los litros, tocá un destino y **Guardar**.
2. **Panel.** En **Leche → Panel** tenés los litros de hoy (por ordeñe y destino), del mes, el promedio y
   los últimos 14 días. Si el día queda por debajo de `LECHE_UMBRAL_LITROS_DIARIOS` (250 L en el ejemplo),
   aparece la alerta.
3. **Repartir litros.** Cargá un lote con destino *Pendiente*, abrilo desde **Lotes** y asigná por ejemplo
   60 L a queso y 25 L a venta: el saldo disponible se recalcula. No te deja asignar más que el saldo.
4. **Listado y filtros.** En **Lotes** filtrá por fechas, destino (incluye "con litros sin destino") y estado.
5. **Corrección de un día anterior.** Como `operador`, abrí un lote de ayer y tocá **Corregir datos**:
   avisa que queda pendiente. Al enviar, el lote pasa a *Corrección pendiente* y los litros no cambian.
6. **Aprobación.** Entrá como `admin`: el panel muestra "1 corrección espera tu aprobación". Abrila,
   compará *Ahora* contra *Propuesto* y aprobá o rechazá con motivo.
7. **Lote cerrado.** Con todo el saldo asignado, **Cerrar lote**. El operador ya no puede editarlo;
   el admin sí, con motivo obligatorio.
8. **Sin señal.** Con el modo avión (o las herramientas del navegador sin red) guardá un lote: queda
   en el teléfono con un aviso amarillo y se envía solo al volver la señal.
9. **Permisos.** Como `ventas`, el módulo Leche no aparece en el menú y la API responde 403.

## Cómo probar la Fase 3 (queso, inventario y ordeñe por vaca)

Si ya tenías la Fase 2 levantada, borrá los datos para que se carguen los nuevos ejemplos:
`docker compose down -v && docker compose up --build`.

1. **Ordeñe por vaca.** Como `operador` (en el celular), **Rodeo → Ordeñe por vaca**. Aparecen las vacas
   en ordeñe; escribí los litros de cada una (Enter pasa a la siguiente) y **Guardar planilla**. El total
   de las vacas es el lote de leche de esa sesión. Volver a guardar la misma planilla no duplica nada, y
   sin señal queda en el teléfono hasta que vuelva.
2. **Tendencia.** En **Rodeo → Vacas** se ve el promedio diario de cada vaca en los últimos 7 días contra
   los 7 anteriores; las que bajan aparecen primero. Tocando una vaca, el gráfico de 30 días.
3. **Iniciar lote (paso 1).** **Queso → Iniciar lote**: marcá los lotes de leche de origen (ajustá los
   litros si no usás todo) y los insumos que vas a usar. Al iniciar, la leche se descuenta y los insumos
   quedan reservados (en **Inventario** se ven como *Reservado*).
4. **Cerrar lote (paso 2).** En el lote, tocá **Cerrar lote** sin kg: no te deja. Cargá los kg obtenidos
   (y la merma, si hubo) y lo que realmente se usó de cada insumo. Mientras escribís ves el rendimiento
   en L/kg y si cae fuera del rango (`QUESO_RENDIMIENTO_MIN_L_KG` / `MAX`, 7 a 11 por defecto).
   Al cerrar, el lote pasa a *Pendiente de aprobación* y el queso entra al inventario "en revisión".
5. **Aprobación.** El operador no ve los botones de aprobar. Como `admin`, en **Queso** aparece el aviso
   de lotes pendientes: **Rechazar** exige un comentario; el operador ve el comentario, corrige y vuelve
   a enviar; **Aprobar** deja el queso disponible para la venta (**Inventario → Queso**).
6. **Trazabilidad.** En cualquier lote de queso: vacas → lotes de leche → lote de queso → insumos (con el
   lote del proveedor) → clientes, más los movimientos de inventario y el historial. Desde un
   lote de leche, la sección *Usado en queso* muestra el otro sentido.
7. **Inventario.** **Inventario → Insumos**: stock, reservado y disponible; registrar una compra con el lote
   del proveedor. Solo el `admin` hace ajustes (con motivo). **Movimientos** muestra todo lo que entró y
   salió; no se puede editar ni borrar.
8. **Cancelar.** Un lote en elaboración se puede cancelar con motivo: los insumos vuelven al stock y la
   leche queda otra vez lista para queso.

## Cómo probar la Fase 4 (ventas, clientes y cuentas por cobrar)

Si ya tenías la Fase 3 levantada, borrá los datos para que se carguen los ejemplos de ventas:
`docker compose down -v && docker compose up --build`. Quedan 5 clientes de ejemplo, 8 ventas y la tabla
de precios inicial (queso Gs. 40.000/kg base, 36.000 mayorista, 34.000 distribuidor, 37.000 desde 20 kg;
leche Gs. 3.500/L, 3.200 desde 100 L).

1. **Registrar venta.** Como `ventas` (en el celular), **Ventas y cobros → Registrar venta**: buscá el
   cliente (o crealo ahí mismo), elegí queso o leche y escribí la cantidad. El total se calcula solo con
   el precio que le corresponde al cliente, se ve cuánto hay disponible y de qué lotes va a salir (primero
   el más viejo). Si pedís más de lo que hay, no te deja.
2. **Inventario y cuenta.** Al registrar, el stock baja en **Inventario → Queso** (o la leche del lote) y
   nace la cuenta por cobrar con el vencimiento según la condición del cliente (contado, 7, 15 o 30 días).
3. **Cobrar.** En la venta, **Registrar cobro** (total o parcial, efectivo o transferencia). Cuando el
   saldo llega a cero y está entregada, pasa a *Cobrada*.
4. **Clientes.** **Clientes** lista con lo que debe cada uno y su última compra. Al entrar a un cliente:
   totales, lotes que recibió y todas sus compras.
5. **Lote → clientes.** En cualquier lote de queso, **Trazabilidad → A quién se vendió**.
6. **Cuentas por cobrar** (solo `admin`): total por cobrar, vencido, vendido y cobrado del mes, quién debe,
   y anular cobros con motivo. El usuario `ventas` no ve esta pestaña (y la API le responde 403).
7. **Precios.** Todos ven la tabla; solo el `admin` la cambia o vende con un precio distinto al de lista.
8. **Anular.** Solo el `admin`, con motivo y sin cobros vigentes: el stock vuelve a su lote.

## Cómo probar la Fase 5 (proveedores, gastos y compras)

Si ya tenías la Fase 4 levantada, borrá los datos para que se carguen los ejemplos:
`docker compose down -v && docker compose up --build`. Quedan 4 proveedores, 2 compras y 5 gastos (dos de
ellos esperando aprobación). El monto que pide aprobación se cambia con `GASTO_MONTO_APROBACION` en el `.env`.

1. **Cargar gasto** (como `operador`, en el celular): **Gastos → Cargar gasto**. Escribí el monto y ya te
   avisa si se aprueba solo o si va al Administrador. Elegí categoría y centro de costo y sacá la foto del
   comprobante con la cámara.
2. **Gasto chico** (Gs. 500.000 o menos): queda *Aprobado (automático)*. **Gasto grande**: queda *Pendiente*.
3. **Solo los propios.** El `operador` ve solo los gastos que cargó; el `admin` ve todos. Filtros por
   categoría, centro de costo, estado y fechas.
4. **Bandeja** (como `admin`): **Aprobaciones**. Tocá un gasto para ver la foto y aprobar o rechazar (el
   rechazo pide comentario). Quien lo cargó ve el comentario y puede corregirlo y reenviarlo.
5. **Proveedores**: **Compras → Proveedores**, alta y edición (nombre, tipo, contacto, teléfono, RUC).
6. **Registrar compra**: proveedor, una o más filas de insumo, cantidad y precio, factura, condición y foto.
   Al confirmar, el stock sube en **Inventario** y nace la cuenta por pagar.
7. **Cuentas por pagar** (solo `admin`): total, vencido, comprado y pagado del mes. Los pagos se registran
   desde la compra y se pueden anular con motivo.
8. **Anular compra**: solo el `admin`, con motivo y sin pagos vigentes. El stock vuelve a bajar.

## Usuarios y roles

Como `admin`, **Usuarios y roles**:

1. **Usuario nuevo**: nombre, usuario para entrar, teléfono, rol (Administrador, Operador o Ventas) y una
   clave provisoria. La primera vez que esa persona entra, el sistema la lleva a **Mi cuenta** para que
   elija una clave propia.
2. En la ficha de un usuario: **Editar o restablecer clave** (la nueva vuelve a ser provisoria) y
   **Desactivar** (ya no puede entrar; no se borra, así su historial queda en la auditoría). El
   Administrador no puede desactivarse ni quitarse el rol a sí mismo, y siempre queda al menos uno activo.
3. **Roles y permisos** muestra qué puede hacer cada rol, módulo por módulo.
4. Cualquier usuario cambia su clave desde **Mi cuenta y clave**, abajo en el menú.

## Pruebas

```bash
docker compose exec backend python -m pytest
```

156 pruebas: login, sesión y refresh, usuarios, permisos y menú por rol, auditoría (mixin, logins,
inmutabilidad), las reglas de la leche (saldo, destinos, correcciones con aprobación, tablero y
alertas), el ordeñe por vaca (suma al lote, reenvío, correcciones, tendencia) y el queso (descuento de
leche e insumos, reservas, consumo real, rendimiento, aprobación solo del Administrador, rechazo y
corrección, cancelación, inventario inmutable y trazabilidad completa por API) y las ventas (precios por
tipo y volumen, no vender más que el stock, descuento de inventario y cuenta por cobrar, cobros, anulación
con devolución del stock, historial del cliente, lote → clientes y permisos de cada rol).

## Desarrollo sin Docker

Necesitás Python 3.12+, Node 22 y PostgreSQL 16 corriendo en `localhost:5432`.

```bash
cp .env.example .env                       # DATABASE_URL apunta a localhost
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
python manage.py migrate
python manage.py seed
python manage.py runserver                  # http://localhost:8000

# en otra terminal
cd frontend
npm install
npm run dev                                 # http://localhost:3000
```

## Estructura

```text
backend/                Django 5.2 + Django REST Framework
  config/               settings, urls
  apps/core/            establecimientos, configuración, auditoría, AuditableModel
  apps/cuentas/         usuarios, roles, permisos, login (JWT), seed
  apps/leche/           lotes de leche, destinos, correcciones, tablero
  apps/rodeo/           animales, ordeñe por vaca y sesión, tendencia
  apps/inventario/      insumos y movimientos de inventario (solo inserción)
  apps/queso/           lotes de queso, aprobación, trazabilidad, stock de leche y queso
  tests/                pruebas (pytest)
frontend/               Next.js 15 + TypeScript + Tailwind
  src/app/login/        pantalla de login
  src/app/(app)/        layout con menú lateral y páginas
  src/lib/              cliente de API y sesión
docker-compose.yml      db + backend + frontend
.env.example            variables de entorno documentadas
```

## API de la Fase 1

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

## API de la Fase 2 (leche)

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

## API de la Fase 3

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

## API de la Fase 4

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

## API de la Fase 5

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

## Cómo se usa lo construido en las próximas fases

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
