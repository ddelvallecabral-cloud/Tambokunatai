# ERP Tambo Kuñatai

Sistema de gestión del tambo: ordeñe, leche, queso paraguayo, inventario, ventas, compras y gastos,
con el dueño como órgano de control y aprobación.

**Estado: Fase 1 — base del sistema** (estructura, base de datos, autenticación, roles y permisos,
auditoría, login y menú lateral). Los módulos de negocio se construyen en las fases siguientes
(ver [DESIGN.md](DESIGN.md)).

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
Con `SEED_DEMO=0` no se crean usuarios de prueba.

Otros accesos:

- API: <http://localhost:8000/api/v1/> (ver lista abajo)
- Panel de respaldo de Django: <http://localhost:8000/admin/> (usuario `admin`)

Para borrar todo y empezar de cero: `docker compose down -v`.

## Pruebas

```bash
docker compose exec backend python -m pytest
```

45 pruebas cubren login, sesión y refresh, registro de usuarios, permisos por rol,
menú por rol, auditoría de logins, el mixin de auditoría y la inmutabilidad de la tabla de auditoría.

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
