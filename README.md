# ERP Tambo Kuñatai

Sistema de gestión del tambo: ordeñe, leche, queso paraguayo, inventario, ventas, compras y gastos,
con el dueño como órgano de control y aprobación. Se usa desde el celular en el campo y desde la
computadora en la oficina.

**Estado: terminado (Fases 1 a 7).** Pendiente solo lo listado en
[Deudas técnicas y funcionalidades futuras](DESIGN.md#deudas-técnicas-conocidas-y-funcionalidades-futuras).

| Documento | Para quién | Qué tiene |
| --------- | ---------- | --------- |
| [MANUAL_OPERADOR.md](MANUAL_OPERADOR.md) | Tamberos, encargados de elaboración y vendedores | Cómo cargar un día: leche, ordeñe por vaca, queso, gastos, ventas y cobros |
| [MANUAL_ADMIN.md](MANUAL_ADMIN.md) | El dueño | Aprobar, revisar trazabilidad, leer reportes, exportar, alertas, usuarios y auditoría |
| [DESPLIEGUE.md](DESPLIEGUE.md) | Quien instale el servidor | Producción con HTTPS, variables, respaldos automáticos, restauración y actualizaciones |
| [DESIGN.md](DESIGN.md) | Programadores | Decisiones del negocio y técnicas, fase por fase, y deudas técnicas |
| [docs/API.md](docs/API.md) | Programadores | Todas las rutas de la API y quién puede usar cada una |

## Probarlo sin instalar nada (GitHub Codespaces)

1. Con tu cuenta de GitHub abierta, entrá a
   **<https://codespaces.new/ddelvallecabral-cloud/Tambokunatai?quickstart=1>** y tocá **Create codespace**.
2. Esperá unos 5 minutos la primera vez: se arma solo (base de datos, sistema y datos de prueba).
3. Se abre una pestaña con la pantalla de login. Si no se abre, en la parte de abajo del editor andá a
   **Ports** y tocá el globo al lado de **ERP Tambo (3000)**.
4. Entrá con `admin` / `Tambo.Admin2026` (o `operador`, `ventas`; ver la tabla de abajo).

Para abrirlo desde el celular: en **Ports**, clic derecho sobre el puerto 3000 → **Port Visibility → Public**
y abrí esa dirección en el teléfono. Cuando termines, cerrá la pestaña: el codespace se apaga solo a los
30 minutos sin uso. Para retomarlo más tarde: <https://github.com/codespaces>.

## Instalación en una computadora (Docker)

Requisitos: Docker Desktop (o Docker Engine + Compose).

```bash
cp .env.example .env        # editá SECRET_KEY antes de usarlo en serio
docker compose up --build
```

Abrí <http://localhost:3000>. Este modo es para probar: trae datos de ejemplo y no usa HTTPS.
Para ponerlo en marcha de verdad, en un servidor con dominio propio, seguí [DESPLIEGUE.md](DESPLIEGUE.md).

Para borrar todo y empezar de cero: `docker compose down -v`.

### Usuarios de prueba (seed)

Con `SEED_DEMO=1` (el valor de `.env.example`) se crean el establecimiento y estos usuarios:

| Usuario    | Clave                | Rol           | Ve en el menú                                              |
| ---------- | -------------------- | ------------- | ---------------------------------------------------------- |
| `admin`    | `Tambo.Admin2026`    | Administrador | Todo: Bandeja de control, Reportes, Auditoría, Usuarios y los módulos de trabajo |
| `operador` | `Tambo.Operador2026` | Operador      | Rodeo, Leche, Queso, Inventario, Compras, Gastos, Reportes (alertas) |
| `ventas`   | `Tambo.Ventas2026`   | Ventas        | Inventario, Ventas y cobros, Gastos, Reportes (mis ventas) |

Las claves se cambian en `.env` (`SEED_CLAVE_*`) antes del primer arranque. Además se cargan datos de
ejemplo: 12 animales, 20 días de ordeñe por vaca, insumos con stock, lotes de queso, clientes, ventas,
proveedores, compras y gastos. Con `SEED_DEMO=0` (producción) no se crea nada de esto: el primer
Administrador se crea con `python manage.py iniciar` (ver [DESPLIEGUE.md](DESPLIEGUE.md)).

## Variables de entorno

Todas van en el archivo `.env` (copia de [.env.example](.env.example), que las explica una por una).

| Variable | Por defecto | Para qué |
| -------- | ----------- | -------- |
| `SECRET_KEY` | — (obligatoria) | Clave secreta de Django. En producción, una larga y aleatoria; el sistema avisa al arrancar si es la de ejemplo |
| `DEBUG` | `False` | `True` solo para programar: muestra errores técnicos |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Nombres con los que se puede entrar al backend |
| `CSRF_TRUSTED_ORIGINS` | vacío | Direcciones completas del sitio (en producción, `https://tu-dominio`) |
| `COOKIE_SECURE` | `False` | `True` con HTTPS: la sesión solo viaja cifrada |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS` | `15` / `7` | Duración del acceso y de la sesión recordada en el celular |
| `JWT_SIGNING_KEY` | igual a `SECRET_KEY` | Clave para firmar las sesiones, si se quiere separada |
| `LOGIN_THROTTLE` | `30/min` | Intentos de entrada por IP |
| `LOGIN_FALLOS_MAX` / `LOGIN_BLOQUEO_MINUTOS` | `5` / `15` | Tras 5 claves mal seguidas, ese usuario espera 15 minutos (0 lo desactiva) |
| `NUM_PROXIES` | `1` | Proxies propios delante de Django que escriben la IP real (ver DESPLIEGUE.md) |
| `HSTS_SEGUNDOS` | `0` | Fuerza HTTPS en el navegador por ese tiempo (en producción lo pone Caddy) |
| `LOG_LEVEL` | `INFO` | Detalle de los registros del servidor |
| `LECHE_UMBRAL_LITROS_DIARIOS` | `250` | Valor inicial de la alerta de producción baja (después se cambia desde Reportes → Alertas) |
| `QUESO_RENDIMIENTO_MIN_L_KG` / `QUESO_RENDIMIENTO_MAX_L_KG` | `7` / `11` | Valor inicial del rango de rendimiento del queso (también se cambia desde Alertas) |
| `GASTO_MONTO_APROBACION` | `500000` | Gastos por encima de este monto esperan la aprobación del Administrador |
| `COMPROBANTE_MAX_MB` | `8` | Tamaño máximo de la foto o PDF de un comprobante |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `tambo` | Base de datos (en producción, una clave fuerte) |
| `DATABASE_URL` | — | Solo al correr el backend fuera de Docker |
| `MEDIA_ROOT` | `backend/media` | Carpeta de las fotos de comprobantes |
| `SEED_DEMO` / `SEED_CLAVE_*` | `1` / ver arriba | Datos y usuarios de prueba |
| `DOMINIO` | — | Solo producción: dominio del sistema (Caddy pide el certificado HTTPS) |
| `RESPALDO_DIR` / `RESPALDO_DIAS` / `RESPALDO_REMOTO` | `respaldos` / `30` / vacío | Solo producción: dónde y por cuánto se guardan los respaldos, y copia fuera del servidor |

## Pruebas

```bash
docker compose exec backend python -m pytest
```

300 pruebas automáticas. Cubren:

- Login, sesión, bloqueo por intentos fallidos y claves.
- Que **toda** la API pida sesión, y que el Operador y Ventas no lleguen a nada del Administrador.
- La auditoría inmutable.
- Las reglas de leche, ordeñe por vaca, queso e inventario:
  - Saldos.
  - Reservas.
  - Aprobaciones.
  - Trazabilidad.
- Ventas, cobros, compras y gastos.
- Los reportes, con importes calculados a mano. Por ejemplo, el estado de resultados cuadra con ventas − gastos − compras.

Además, las pantallas se probaron de punta a punta con un navegador automático:

- **Celular, un día completo.** Leche de la mañana y de la tarde vaca por vaca, un lote de queso iniciado y cerrado, un gasto con foto, una venta con cobro y la aprobación del Administrador.
- **Celular del Operador.** Todas sus pantallas entran sin desbordar el ancho.
- **Reportes.** Exportes en PDF y Excel.

## Desarrollo sin Docker

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
backend/                Django 5.2 + Django REST Framework + PostgreSQL 16
  config/               settings, urls
  apps/core/            establecimiento, configuración, auditoría inmutable, AuditableModel, errores
  apps/cuentas/         usuarios, roles, permisos, login (JWT), seed
  apps/rodeo/           animales, ordeñe por vaca y sesión, tendencia
  apps/leche/           lotes de leche, destinos, correcciones, panel
  apps/inventario/      insumos y movimientos de inventario (solo inserción)
  apps/queso/           lotes de queso, aprobación, trazabilidad
  apps/ventas/          clientes, precios, ventas, cuentas por cobrar y cobros
  apps/compras/         proveedores, compras, cuentas por pagar y pagos
  apps/gastos/          gastos con comprobante y aprobación
  apps/reportes/        tablero, reportes, exportes PDF/Excel, alertas, bandeja de control
  tests/                pruebas (pytest)
frontend/               Next.js 15 + TypeScript + Tailwind (web que se usa desde el celular)
  src/app/(app)/        pantallas
  src/components/       piezas compartidas (tablero, gráficos, confirmaciones, formularios)
  src/lib/              cliente de API, sesión, formatos, cola sin señal
deploy/                 Caddyfile (HTTPS), respaldo.sh y restaurar.sh
docs/                   API.md y capturas de los manuales
docker-compose.yml      para probar (con datos de ejemplo)
docker-compose.prod.yml para producción (HTTPS, sin datos de ejemplo)
.env.example            variables de entorno documentadas
```
