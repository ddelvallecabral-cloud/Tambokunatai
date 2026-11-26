"""Avisos al arrancar si la configuración no es apta para producción."""
from django.conf import settings
from django.core.checks import Warning, register

CLAVE_DE_EJEMPLO = "cambiame"


@register(deploy=False)
def configuracion_segura(app_configs, **kwargs):
    avisos = []
    clave = settings.SECRET_KEY or ""
    if CLAVE_DE_EJEMPLO in clave or len(clave) < 40:
        avisos.append(Warning(
            "SECRET_KEY es la de ejemplo o es demasiado corta.",
            hint='Generá una con: python -c "import secrets; print(secrets.token_urlsafe(50))" y ponela en el .env.',
            id="tambo.W001"))
    if not settings.DEBUG and not settings.SESSION_COOKIE_SECURE and any(
            o.startswith("https://") for o in settings.CSRF_TRUSTED_ORIGINS):
        avisos.append(Warning(
            "El sitio usa HTTPS pero COOKIE_SECURE=False: la sesión podría viajar sin cifrar.",
            hint="Poné COOKIE_SECURE=True en el .env de producción.", id="tambo.W002"))
    return avisos
