#!/bin/sh
# Arranque del contenedor `web`: espera a la base, migra y sirve con gunicorn.
set -eu

export DJANGO_SETTINGS_MODULE=config.settings

# Falla de inmediato si la configuración es inválida (por ejemplo, sin clave):
# no tiene caso esperar a la base con un ajuste que nunca va a arrancar.
python -c "import django; django.setup()"

echo "Esperando a la base de datos en ${DB_HOST:-127.0.0.1}:${DB_PORT:-3306}..."
intento=0
until python - <<'PY'
import sys

import django

django.setup()
from django.db import connection
from django.db.utils import OperationalError

try:
    connection.ensure_connection()
except OperationalError as error:
    print(f'  todavía no responde: {error}', file=sys.stderr)
    sys.exit(1)
PY
do
    intento=$((intento + 1))
    if [ "$intento" -ge 30 ]; then
        echo "La base de datos no respondió después de 30 intentos." >&2
        exit 1
    fi
    sleep 2
done
echo "La base de datos respondió."

# Crea las tablas y el disparador de la bitácora (migración 0002).
python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 30 \
    --access-logfile -
