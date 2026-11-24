#!/bin/sh
# Arranque en producción (Render).
set -e

# El plan gratuito de Render no tiene comando previo al despliegue: las migraciones se aplican
# al iniciar. Si no hay ninguna pendiente, tarda menos de un segundo.
python manage.py migrate --noinput

# Un proceso con varios hilos: la instancia gratuita tiene 512 MB y 0,1 CPU, y la API pasa la mayor
# parte del tiempo esperando a MongoDB. Con un solo proceso, el límite de solicitudes es exacto.
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --threads 4 \
    --timeout 60 \
    --access-logfile -
