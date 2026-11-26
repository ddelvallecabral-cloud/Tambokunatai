"""Usuario y datos de la petición en curso, accesibles desde los modelos.

Se guardan en ContextVar (seguro con hilos y async). Los completa:
- RequestIdMiddleware: request_id, IP y dispositivo.
- JWTConContexto: el usuario autenticado (DRF autentica después del middleware).
"""
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class ContextoPeticion:
    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    usuario: object | None = None
    ip: str | None = None
    dispositivo: str = ""


_contexto: ContextVar[ContextoPeticion | None] = ContextVar("contexto_peticion", default=None)


def contexto_actual() -> ContextoPeticion:
    ctx = _contexto.get()
    if ctx is None:
        ctx = ContextoPeticion()
        _contexto.set(ctx)
    return ctx


def iniciar_contexto(**datos) -> object:
    return _contexto.set(ContextoPeticion(**datos))


def terminar_contexto(token) -> None:
    _contexto.reset(token)


def usuario_actual():
    usuario = contexto_actual().usuario
    if usuario is not None and getattr(usuario, "is_authenticated", False):
        return usuario
    return None


def fijar_usuario(usuario) -> None:
    contexto_actual().usuario = usuario
