from .contexto import iniciar_contexto, terminar_contexto


def ip_cliente(request) -> str | None:
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada:
        return reenviada.split(",")[0].strip()
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
