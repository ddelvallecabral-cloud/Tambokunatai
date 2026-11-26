from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("gastos", views.GastoViewSet, basename="gasto")

urlpatterns = [path("aprobaciones/pendientes", views.bandeja, name="aprobaciones-pendientes"), *router.urls]
