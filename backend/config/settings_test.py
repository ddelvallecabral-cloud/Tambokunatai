from .settings import *  # noqa: F401,F403
from .settings import INSTALLED_APPS, PASSWORD_HASHERS, REST_FRAMEWORK

INSTALLED_APPS = [*INSTALLED_APPS, "tests.app_prueba"]
# Hash rápido solo para pruebas.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher", *PASSWORD_HASHERS]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"login": "1000/min"}}
