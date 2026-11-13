"""
Configuracion del prototipo de auditoria de indicadores.

Contexto: producto tecnologico de la monografia "Parametros de gobernanza
de datos para un prototipo de Inteligencia Artificial enfocado en auditar
los indicadores del Plan de Accion - Ministerio de las Culturas, las Artes
y los Saberes (2025-2026)". Arquitectura monolitica, ejecucion 100% local
(sin nube, sin APIs externas) segun el criterio de "operabilidad local"
definido en la seccion de validacion del prototipo.
"""

from pathlib import Path
import environ

# En redes corporativas con inspeccion TLS (proxy/antivirus), el root CA
# inyectado esta en el almacen de Windows pero no en el bundle de certifi
# que usan httpx/huggingface_hub. Se usa el almacen del sistema operativo
# para las descargas de modelos (sentence-transformers) y llamadas locales.
import truststore

truststore.inject_into_ssl()

BASE_DIR = Path(__file__).resolve().parent.parent

import sys

from django.core.exceptions import ImproperlyConfigured

# Seguro por defecto: DEBUG apagado. Para desarrollo local se activa con DEBUG=True
# (variable de entorno o archivo .env; ver .env.example).
env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

CLAVES_NO_SEGURAS = {"django-insecure-dev-key-change-me", "change-me-in-local-env"}
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-change-me")
DEBUG = env("DEBUG")
# Fuera de desarrollo no se arranca con una clave de ejemplo (las pruebas automaticas si pueden).
if not DEBUG and SECRET_KEY in CLAVES_NO_SEGURAS and sys.argv[1:2] != ["test"]:
    raise ImproperlyConfigured(
        "Defina DJANGO_SECRET_KEY con un valor propio, o active DEBUG=True solo para desarrollo local (ver .env.example)."
    )
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Sesion y cookies. Las cookies seguras exigen HTTPS: se activan con COOKIES_SEGURAS=True tras un proxy con TLS.
SESSION_COOKIE_AGE = env.int("SESION_DURACION_SEGUNDOS", default=8 * 60 * 60)  # 8 horas
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env.bool("COOKIES_SEGURAS", default=False)
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Carga de archivos: tamano maximo (MB) del reporte; los formatos permitidos se validan en el formulario.
CARGA_TAMANO_MAXIMO_MB = env.int("CARGA_TAMANO_MAXIMO_MB", default=25)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del dominio (monolito modular, un app por objetivo especifico)
    "apps.gobernanza",
    "apps.ingesta",
    "apps.nlp_engine",
    "apps.auditoria",
    "apps.dashboard",
    "apps.reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

# Base de datos: PostgreSQL local (tecnologia obligatoria del prototipo).
# DATABASE_URL por defecto asume una instancia local sin credenciales en la nube.
# USE_SQLITE_LOCAL es solo para verificacion de codigo mientras se instala
# PostgreSQL (evita problemas de URL-encoding de rutas con espacios en Windows).
if env.bool("USE_SQLITE_LOCAL", default=False):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL",
            default="postgres://postgres:postgres@localhost:5432/auditoria_indicadores",
        )
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Configuracion del dominio: gobernanza, NLP y ejecucion local
# ---------------------------------------------------------------------------

# Motor de embeddings (sentence-transformers; Reimers & Gurevych, 2019): unico
# modelo de inteligencia artificial del prototipo, ejecutado localmente.
# Modelo multilingue por defecto para textos en espanol.
NLP_ENGINE = {
    "EMBEDDING_MODEL": env(
        "EMBEDDING_MODEL", default="paraphrase-multilingual-mpnet-base-v2"
    ),
    "UMBRAL_DUPLICIDAD": env.float("UMBRAL_DUPLICIDAD", default=0.85),
    "UMBRAL_CLONACION_TEXTUAL": env.float("UMBRAL_CLONACION_TEXTUAL", default=0.95),
}


# Bandera de "operabilidad local": el prototipo no debe requerir, para
# operar, que los datos institucionales salgan de la infraestructura propia.
# Se registra en cada corrida de auditoria como parte de la evidencia de
# trazabilidad (ver apps.gobernanza.models.EjecucionAuditoria).
EJECUCION_100_POR_CIENTO_LOCAL = True

# Privacidad: los reportes institucionales pueden traer datos personales (por
# ejemplo, nombres y documentos de contratistas) en columnas que el prototipo no
# usa. Por defecto, el archivo original se elimina del disco apenas se procesa;
# el historial conserva su nombre, fecha y resultado. Active la conservacion solo
# si necesita volver a procesar el mismo archivo.
CONSERVAR_ARCHIVO_ORIGINAL = env.bool("CONSERVAR_ARCHIVO_ORIGINAL", default=False)

# Autenticacion: el auditor y el administrador ingresan con usuario y contrasena.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:inicio"
LOGOUT_REDIRECT_URL = "login"

# Las etiquetas de mensajes de Django coinciden con las clases de alerta de Bootstrap.
from django.contrib.messages import constants as _mensajes  # noqa: E402

MESSAGE_TAGS = {_mensajes.ERROR: "danger"}
