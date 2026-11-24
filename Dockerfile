FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Usuario sin privilegios: los archivos creados en el contenedor no quedan a nombre de root
RUN useradd --create-home --uid 1000 app

COPY --chown=app:app . .

# Archivos estáticos del admin, incluidos en la imagen. collectstatic no se conecta a la base:
# los valores de estas variables solo existen para que la configuración se pueda cargar.
RUN DJANGO_SECRET_KEY=collectstatic MONGODB_URI=mongodb://localhost \
    python manage.py collectstatic --noinput

USER app

EXPOSE 8000

# Producción: migraciones y gunicorn (scripts/start.sh). En desarrollo, docker-compose-dev.yml
# reemplaza este comando por runserver.
CMD ["sh", "scripts/start.sh"]

