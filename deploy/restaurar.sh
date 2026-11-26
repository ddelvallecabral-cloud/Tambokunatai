#!/bin/sh
# Restaura un respaldo hecho con respaldo.sh. REEMPLAZA todos los datos actuales por los del respaldo.
#
# Uso (desde la carpeta del sistema):
#   ./deploy/restaurar.sh respaldos/tambo_20261126_0200.dump [respaldos/comprobantes_20261126_0200.tar.gz]
#
# Pide escribir SI antes de tocar nada. Mientras restaura, el sistema queda detenido unos minutos.

set -eu

cd "$(dirname "$0")/.."
[ -f .env ] && . ./.env

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
USUARIO_DB="${POSTGRES_USER:-tambo}"
BASE="${POSTGRES_DB:-tambo}"
DUMP="${1:-}"
FOTOS="${2:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Indicá el archivo .dump a restaurar. Los disponibles:" >&2
  ls -1t respaldos/tambo_*.dump 2>/dev/null | head -10 >&2 || true
  exit 1
fi

echo "Vas a reemplazar TODOS los datos actuales por los del respaldo $DUMP."
[ -n "$FOTOS" ] && echo "También se reemplazan los comprobantes por los de $FOTOS."
printf "Escribí SI (en mayúsculas) para seguir: "
read -r RESPUESTA
[ "$RESPUESTA" = "SI" ] || { echo "Cancelado. No se tocó nada."; exit 1; }

echo "Deteniendo el sistema..."
$COMPOSE stop backend frontend

echo "Restaurando la base de datos..."
$COMPOSE exec -T db dropdb -U "$USUARIO_DB" --if-exists --force "$BASE"
$COMPOSE exec -T db createdb -U "$USUARIO_DB" "$BASE"
$COMPOSE exec -T db pg_restore -U "$USUARIO_DB" -d "$BASE" --no-owner --exit-on-error < "$DUMP"

if [ -n "$FOTOS" ]; then
  echo "Restaurando los comprobantes..."
  $COMPOSE run --rm --no-deps -T --entrypoint sh backend -c "rm -rf /app/media/* && tar xzf - -C /app" < "$FOTOS"
fi

echo "Levantando el sistema..."
$COMPOSE start backend frontend
echo "Listo. Entrá al sistema y revisá en Auditoría → Verificar integridad que todo esté en orden."
