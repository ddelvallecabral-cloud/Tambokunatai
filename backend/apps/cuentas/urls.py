from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("roles", views.RolViewSet, basename="rol")

urlpatterns = [
    path("auth/login", views.login, name="auth-login"),
    path("auth/refresh", views.refrescar, name="auth-refresh"),
    path("auth/logout", views.logout, name="auth-logout"),
    path("auth/me", views.perfil, name="auth-me"),
    path("auth/cambiar-clave", views.cambiar_clave, name="auth-cambiar-clave"),
    *router.urls,
]
