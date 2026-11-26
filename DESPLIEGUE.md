# Puesta en marcha en producción

Cómo dejar el sistema funcionando en internet, con HTTPS, y cómo hacer y recuperar respaldos.
Está escrito para quien instala el servidor (alguien con nociones de Linux); el dueño no necesita
seguirlo, pero sí conviene que sepa dónde quedan los respaldos (ver [Respaldos](#respaldos)).

## Qué hace falta

- Un servidor Linux (VPS) con 2 GB de RAM y 20 GB de disco. Alcanza con el plan más chico de cualquier
  proveedor (DigitalOcean, Hetzner, Contabo, o uno local).
- Un dominio o subdominio apuntando a la IP del servidor, por ejemplo `tambo.midominio.com.py`
  (registro tipo A en el panel del dominio).
- Docker y Docker Compose instalados: `curl -fsSL https://get.docker.com | sh`.
- Los puertos 80 y 443 abiertos (Caddy los usa para el certificado HTTPS y para atender).

## Instalación

```bash
# 1. Bajar el sistema
sudo mkdir -p /opt/tambo && sudo chown $USER /opt/tambo
git clone https://github.com/ddelvallecabral-cloud/Tambokunatai.git /opt/tambo
cd /opt/tambo

# 2. Configurar
cp .env.example .env
nano .env
```

En el `.env` cambiá **como mínimo** estas líneas (el resto puede quedar como está):

| Variable | Valor en producción |
| -------- | ------------------- |
| `SECRET_KEY` | Una clave nueva: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DOMINIO` | El dominio, sin `https://`: `tambo.midominio.com.py` (agregá la línea) |
| `POSTGRES_PASSWORD` | Una clave fuerte para la base de datos |
| `SEED_DEMO` | `0` (sin datos de prueba) |
| `GASTO_MONTO_APROBACION` | El monto a partir del cual un gasto espera tu aprobación |

`DEBUG`, `COOKIE_SECURE`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `NUM_PROXIES` los fija solo
`docker-compose.prod.yml` a partir de `DOMINIO`; no hace falta tocarlos.

```bash
# 3. Levantar (la primera vez tarda unos minutos en construir)
docker compose -f docker-compose.prod.yml up -d --build

# 4. Crear el tambo y el primer Administrador (pregunta nombre, usuario y clave)
docker compose -f docker-compose.prod.yml exec backend python manage.py iniciar
```

Entrá a `https://tu-dominio` con ese usuario. Caddy pide el certificado HTTPS solo la primera vez que
alguien entra (tarda unos segundos). Después, desde el sistema:

1. **Usuarios y roles**: creá un usuario por persona (Operador para tamberos y elaboración, Ventas para
   quien vende y cobra). Cada uno entra con una clave provisoria y elige la suya.
2. **Ventas → Precios**: cargá el precio del queso y de la leche por tipo de cliente.
3. **Inventario**: cargá los insumos (cuajo, sal, cloruro, fermento, bolsas) con su stock mínimo.
4. **Rodeo**: cargá las vacas en ordeñe si van a registrar el ordeñe por vaca.
5. **Reportes → Alertas**: ajustá los litros mínimos por día y el rango de rendimiento del queso.

### Cómo queda armado

```text
celular / computadora ──HTTPS──▶ Caddy (80/443) ──▶ frontend Next.js ──▶ backend Django ──▶ PostgreSQL
                                  certificado y                                 │
                                  encabezados de seguridad                      └─▶ carpeta de comprobantes
```

Solo Caddy queda expuesto a internet. La base de datos, el backend y el frontend están en la red interna
de Docker. Caddy reescribe `X-Forwarded-For` con la IP real de cada celular, así la auditoría y el límite
de intentos de entrada ven quién se conecta de verdad (por eso `NUM_PROXIES=1`).

## Respaldos

Hay dos cosas que respaldar: la **base de datos** (todo lo cargado) y la carpeta de **comprobantes**
(fotos y PDF de gastos y compras). El script `deploy/respaldo.sh` hace las dos y verifica que el
respaldo de la base se pueda leer antes de darlo por bueno.

```bash
cd /opt/tambo && ./deploy/respaldo.sh
```

Deja en `/opt/tambo/respaldos/`:

- `tambo_AAAAMMDD_HHMM.dump`: la base de datos completa.
- `comprobantes_AAAAMMDD_HHMM.tar.gz`: las fotos.

Borra solo los que tienen más de 30 días (`RESPALDO_DIAS` en el `.env`).

### Respaldo automático todos los días

```bash
crontab -e
```

y agregá esta línea (respaldo a las 2 de la mañana, con un registro de cada corrida):

```text
0 2 * * * cd /opt/tambo && ./deploy/respaldo.sh >> respaldos/respaldo.log 2>&1
```

Para comprobar que anda: al día siguiente, `ls -lh /opt/tambo/respaldos/` y `tail respaldos/respaldo.log`.

### Copia fuera del servidor (muy recomendado)

Un respaldo que vive solo en el mismo servidor se pierde si el servidor se rompe o el proveedor lo borra.
El script copia los archivos del día a Google Drive (o Dropbox, OneDrive, S3…) con
[rclone](https://rclone.org):

```bash
sudo apt install rclone
rclone config            # crear un destino llamado "drive" y autorizar la cuenta de Google
echo 'RESPALDO_REMOTO=drive:respaldos-tambo' >> .env
./deploy/respaldo.sh     # probarlo una vez a mano
```

### Restaurar un respaldo

`deploy/restaurar.sh` **reemplaza todos los datos actuales** por los del respaldo. Pide escribir `SI` antes
de tocar nada y detiene el sistema unos minutos mientras restaura.

```bash
cd /opt/tambo
ls -lt respaldos/                                   # elegir el respaldo
./deploy/restaurar.sh respaldos/tambo_20261126_0200.dump respaldos/comprobantes_20261126_0200.tar.gz
```

Después entrá como Administrador a **Auditoría → Verificar integridad**: tiene que decir *Intacta*.
El procedimiento se probó de punta a punta: respaldo, restauración en una base nueva, mismos registros
y cadena de auditoría intacta.

Para mudar el sistema a otro servidor: instalá ahí siguiendo esta guía (sin correr `iniciar`), copiá los
dos archivos del último respaldo y restauralos.

## Actualizar a una versión nueva

```bash
cd /opt/tambo
./deploy/respaldo.sh                                   # siempre un respaldo antes
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Las migraciones de la base corren solas al arrancar el backend.

## Revisar que todo ande

| Qué | Cómo |
| --- | ---- |
| Estado de los servicios | `docker compose -f docker-compose.prod.yml ps` (todos `running`) |
| El sistema responde | `curl https://tu-dominio/api/v1/salud` → `{"estado":"ok"}` |
| Errores del servidor | `docker compose -f docker-compose.prod.yml logs --tail=100 backend` |
| Avisos de configuración | Al arrancar, el backend avisa si `SECRET_KEY` es la de ejemplo (`tambo.W001`) o si falta `COOKIE_SECURE` con HTTPS (`tambo.W002`) |
| Espacio en disco | `df -h /` y `du -sh /opt/tambo/respaldos` |
| Auditoría sin alterar | En el sistema: **Auditoría → Verificar integridad** |

## Seguridad (resumen)

- Claves guardadas con Argon2. Mínimo 8 caracteres, no comunes, no solo números y no parecidas al usuario.
- Sesión de 15 minutos que se renueva sola mientras se usa, con una cookie `httpOnly` y `Secure` que el
  JavaScript no puede leer. Al cerrar sesión, la cookie queda invalidada.
- Dos frenos al adivinar claves: 30 intentos por minuto por IP, y 15 minutos de bloqueo para un usuario
  tras 5 claves mal seguidas.
- HTTPS obligatorio (HSTS), protección contra iframes (clickjacking) y contra la detección de tipos de archivo.
- Toda la API exige sesión, y cada ruta exige además el permiso del rol (hay pruebas automáticas que lo
  revisan ruta por ruta).
- La auditoría no se puede modificar ni borrar desde el sistema (triggers de PostgreSQL), y una cadena de
  hashes detecta si alguien la tocó directo en la base.
- Los comprobantes no son públicos: solo se bajan con sesión.
