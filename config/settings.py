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

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
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

# Motor de embeddings (sentence-transformers, independiente del LLM segun
# la decision arquitectonica: trazabilidad metodologica con Reimers &
# Gurevych, 2019). Modelo multilingue por defecto para textos en espanol.
NLP_ENGINE = {
    "EMBEDDING_MODEL": env(
        "EMBEDDING_MODEL", default="paraphrase-multilingual-mpnet-base-v2"
    ),
    "UMBRAL_DUPLICIDAD": env.float("UMBRAL_DUPLICIDAD", default=0.85),
    "UMBRAL_DIVERGENCIA": env.float("UMBRAL_DIVERGENCIA", default=0.80),
    "UMBRAL_CLONACION_TEXTUAL": env.float("UMBRAL_CLONACION_TEXTUAL", default=0.95),
}

# Ollama + Qwen2.5: usado exclusivamente para clasificacion metodologica,
# resolucion de casos ambiguos, y generacion de explicaciones de hallazgos.
# Nunca para el calculo de similitud semantica (eso es responsabilidad de
# NLP_ENGINE / sentence-transformers).
OLLAMA = {
    "HOST": env("OLLAMA_HOST", default="http://localhost:11434"),
    "MODEL": env("OLLAMA_MODEL", default="qwen2.5:7b"),
    "TIMEOUT_SECONDS": env.int("OLLAMA_TIMEOUT_SECONDS", default=120),
}

# Bandera de "operabilidad local": el prototipo no debe requerir, para
# operar, que los datos institucionales salgan de la infraestructura propia.
# Se registra en cada corrida de auditoria como parte de la evidencia de
# trazabilidad (ver apps.gobernanza.models.EjecucionAuditoria).
EJECUCION_100_POR_CIENTO_LOCAL = True

# Celery (procesamiento asincrono de embeddings por lote y llamadas al LLM,
# para no bloquear el ciclo request/response de Django).
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
