from rest_framework_simplejwt.authentication import JWTAuthentication

from .contexto import fijar_usuario


class JWTConContexto(JWTAuthentication):
    """JWT estándar que además deja el usuario en el contexto para la auditoría automática."""

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is not None:
            fijar_usuario(resultado[0])
        return resultado
