#!/bin/sh
# Respaldo de la base de datos y de las fotos de comprobantes del ERP del tambo.
#
# Uso (desde la carpeta del sistema, la que tiene docker-compose.prod.yml):
#   ./deploy/respaldo.sh
#
# Deja en respaldos/ (o en RESPALDO_DIR):
#   tambo_AAAAMMDD_HHMM.dump          base de datos completa (formato de pg_dump, se restaura con restaurar.sh)
#   comprobantes_AAAAMMDD_HHMM.tar.gz fotos y PDF de gastos y compras
# Borra los respaldos con más de RESPALDO_DIAS días (30 por defecto).
# Si RESPALDO_REMOTO está definido (un destino de rclone, p. ej. "drive:respaldos-tambo"), además copia
# los archivos del día fuera del servidor. Un respaldo que vive solo en el mismo servidor no sirve si el
# servidor se rompe.
#
# Programarlo todos los días a las 2 de la mañana (crontab -e):
#   0 2 * * * cd /opt/tambo && ./deploy/respaldo.sh >> respaldos/respaldo.log 2>&1

set -eu

cd "$(dirname "$0")/.."
[ -f .env ] && . ./.env

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
DESTINO="${RESPALDO_DIR:-respaldos}"
DIAS="${RESPALDO_DIAS:-30}"
USUARIO_DB="${POSTGRES_USER:-tambo}"
BASE="${POSTGRES_DB:-tambo}"
MARCA="$(date +%Y%m%d_%H%M)"

mkdir -p "$DESTINO"
DUMP="$DESTINO/tambo_$MARCA.dump"
FOTOS="$DESTINO/comprobantes_$MARCA.tar.gz"

echo "$(date '+%F %T') Respaldando la base de datos en $DUMP"
$COMPOSE exec -T db pg_dump -U "$USUARIO_DB" -d "$BASE" --format=custom --no-owner > "$DUMP.parcial"

# Un respaldo vacío o roto no se queda con el nombre definitivo.
if [ ! -s "$DUMP.parcial" ] || ! $COMPOSE exec -T db pg_restore --list < "$DUMP.parcial" > /dev/null 2>&1; then
  echo "ERROR: el respaldo de la base no se puede leer. Revisá que el sistema esté levantado." >&2
  mv "$DUMP.parcial" "$DUMP.fallido"
  exit 1
fi
mv "$DUMP.parcial" "$DUMP"

echo "$(date '+%F %T') Respaldando los comprobantes en $FOTOS"
$COMPOSE exec -T backend tar czf - -C /app media > "$FOTOS"

echo "$(date '+%F %T') Borrando respaldos de más de $DIAS días"
find "$DESTINO" -maxdepth 1 -type f \( -name 'tambo_*.dump' -o -name 'comprobantes_*.tar.gz' -o -name '*.fallido' \) \
  -mtime +"$DIAS" -exec rm -f {} +

if [ -n "${RESPALDO_REMOTO:-}" ]; then
  echo "$(date '+%F %T') Copiando fuera del servidor a $RESPALDO_REMOTO"
  rclone copy "$DUMP" "$RESPALDO_REMOTO"
  rclone copy "$FOTOS" "$RESPALDO_REMOTO"
fi

echo "$(date '+%F %T') Listo: $(du -h "$DUMP" | cut -f1) de base de datos, $(du -h "$FOTOS" | cut -f1) de comprobantes."
