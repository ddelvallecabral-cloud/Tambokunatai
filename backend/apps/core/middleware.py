from .contexto import iniciar_contexto, terminar_contexto


def ip_cliente(request) -> str | None:
    """IP real del cliente detrás de NUM_PROXIES proxies propios (en producción, Caddy: ver docker-compose.prod.yml).

    Se toma la dirección que agregó nuestro proxy más externo, no la primera de la lista: esa la puede
    inventar cualquiera mandando su propio X-Forwarded-For.
    """
    from django.conf import settings

    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    if reenviada and proxies:
        direcciones = [d.strip() for d in reenviada.split(",") if d.strip()]
        if direcciones:
            return direcciones[-min(proxies, len(direcciones))]
    return request.META.get("REMOTE_ADDR")


class RequestIdMiddleware:
    """Abre un contexto por petición para que la auditoría sepa quién, desde dónde y en qué operación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = iniciar_contexto(
            ip=ip_cliente(request),
            dispositivo=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
        try:
            return self.get_response(request)
        finally:
            terminar_contexto(token)
