# ERP Tambo Kuñatai

Sistema de gestión del tambo: ordeñe, leche, queso paraguayo, inventario, ventas, compras y gastos,
con el dueño como órgano de control y aprobación.

**Estado: Fase 2 — producción de leche.** Fase 1 (base, login, roles, auditoría) y Fase 2 (registro
diario de leche, destinos, correcciones con aprobación, panel y alertas) terminadas.
Plan y decisiones en [DESIGN.md](DESIGN.md).

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
El seed también carga 20 días de ordeñes de ejemplo (ayer queda bajo, para que se vea la alerta).
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

## Pruebas

```bash
docker compose exec backend python -m pytest
```

80 pruebas: login, sesión y refresh, usuarios, permisos y menú por rol, auditoría (mixin, logins,
inmutabilidad) y las reglas de negocio de la leche (saldo, destinos, duplicados, correcciones con
aprobación, lotes cerrados, resumen diario, tablero y alertas).

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
