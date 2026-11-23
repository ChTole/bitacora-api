"""
Configuración de Bitácora API.

Todos los valores que cambian entre entornos se leen de variables de entorno
(ver .env.example). En desarrollo las carga Docker Compose desde .env;
en producción se definen en el panel de Render.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ───────────── Variables de entorno ─────────────

def env(name, default=None):
    """Valor de una variable de entorno. Sin valor por defecto, es obligatoria."""
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Falta la variable de entorno {name}.")
    return value


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# ───────────── Seguridad ─────────────

SECRET_KEY = env("DJANGO_SECRET_KEY")

# Por defecto, apagado: si falta la variable, el servidor arranca en modo seguro
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

if not DEBUG:
    # Render recibe HTTPS y reenvía la solicitud a Django por HTTP, con este encabezado
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# ───────────── Aplicaciones ─────────────

INSTALLED_APPS = [
    # Versiones de las apps de Django adaptadas a MongoDB (ver config/apps.py)
    "config.apps.MongoAdminConfig",
    "config.apps.MongoAuthConfig",
    "config.apps.MongoContentTypesConfig",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_mongodb_backend",
    # Terceros
    "rest_framework",
    "corsheaders",
    # Propias
    "telemetry",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS va antes de cualquier middleware que pueda generar una respuesta
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# Plantillas: solo las usa el admin
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ───────────── Base de datos ─────────────

DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": env("MONGODB_URI"),
        "NAME": env("MONGODB_DB_NAME", "bitacora"),
    },
}

DATABASE_ROUTERS = ["django_mongodb_backend.routers.MongoRouter"]

DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"

MIGRATION_MODULES = {
    "admin": "mongo_migrations.admin",
    "auth": "mongo_migrations.auth",
    "contenttypes": "mongo_migrations.contenttypes",
}


# ───────────── Contraseñas del admin ─────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ───────────── Idioma y zona horaria ─────────────

LANGUAGE_CODE = "es-ar"   # idioma del admin

# Las fechas se guardan y se responden en UTC, como indica el contrato
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ───────────── Archivos estáticos (solo los del admin) ─────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ───────────── Django REST Framework ─────────────

REST_FRAMEWORK = {
    # La autenticación por clave de API se agrega con los endpoints del contrato
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    # La API responde solo JSON. La interfaz navegable de DRF queda disponible en desarrollo.
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    # Errores con el formato del contrato: { "error": { "code", "message" } }
    "EXCEPTION_HANDLER": "telemetry.exceptions.contract_exception_handler",
}


# ───────────── CORS ─────────────

# Solo las rutas de la API: el admin no se usa desde otros dominios
CORS_URLS_REGEX = r"^/(v1|stats)/.*$"
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_HEADERS = ["content-type", "x-api-key"]
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]

if DEBUG:
    # En desarrollo, cualquier puerto local (por ejemplo, el servidor de Build and Run de Unity)
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"]
