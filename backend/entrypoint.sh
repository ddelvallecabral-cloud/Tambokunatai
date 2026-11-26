#!/bin/sh
set -e

echo "Esperando a PostgreSQL..."
python manage.py esperar_db

python manage.py migrate --noinput
python manage.py collectstatic --noinput -v0

if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed
fi

exec "$@"
