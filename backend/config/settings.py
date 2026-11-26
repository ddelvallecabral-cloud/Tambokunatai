"""Configuración del ERP del tambo. Todo valor sensible viene de variables de entorno."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    COOKIE_SECURE=(bool, False),
    JWT_ACCESS_MINUTES=(int, 15),
    JWT_REFRESH_DAYS=(int, 7),
)
environ.Env.read_env(BASE_DIR.parent / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.core",
    "apps.cuentas",
    "apps.leche",
    "apps.rodeo",
    "apps.inventario",
    "apps.queso",
    "apps.ventas",
    "apps.compras",
    "apps.gastos",
    "apps.reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
            ]
        },
    }
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

AUTH_USER_MODEL = "cuentas.Usuario"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Asuncion"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.autenticacion.JWTConContexto"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.vistas.Paginacion",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE", default="30/min")},
    # Cantidad de proxies delante (Next.js) para tomar la IP real del cliente de X-Forwarded-For.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=1),
    "EXCEPTION_HANDLER": "apps.core.excepciones.manejador_excepciones",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "uid",
}

# Cookie donde viaja el refresh token (httpOnly: el JavaScript del navegador no puede leerlo).
REFRESH_COOKIE = {
    "key": "tambo_refresh",
    "path": "/api/v1/auth/",
    "httponly": True,
    "secure": env("COOKIE_SECURE"),
    "samesite": "Lax",
}

# Alerta del panel de leche: si los litros de un día completo quedan por debajo de este valor.
# 0 o vacío desactiva la alerta.
LECHE_UMBRAL_LITROS_DIARIOS = env.float("LECHE_UMBRAL_LITROS_DIARIOS", default=0) or None
# Rango esperado de rendimiento del queso, en litros de leche por kg de queso. Fuera del rango, alerta.
QUESO_RENDIMIENTO_MIN_L_KG = env.float("QUESO_RENDIMIENTO_MIN_L_KG", default=7.0)
QUESO_RENDIMIENTO_MAX_L_KG = env.float("QUESO_RENDIMIENTO_MAX_L_KG", default=11.0)

# Gastos: por encima de este monto (Gs.) quedan pendientes de aprobación del Administrador.
GASTO_MONTO_APROBACION = env.int("GASTO_MONTO_APROBACION", default=500_000)

# Fotos de comprobantes. No se sirven como archivos públicos: se bajan por la API con permiso.
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(BASE_DIR / "media")))
COMPROBANTE_MAX_MB = env.int("COMPROBANTE_MAX_MB", default=8)
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
