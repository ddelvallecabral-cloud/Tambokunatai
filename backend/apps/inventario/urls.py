from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("insumos", views.InsumoViewSet, basename="insumo")
router.register("movimientos-inventario", views.MovimientoViewSet, basename="movimiento-inventario")

urlpatterns = [
    path("inventario/leche", views.inventario_leche, name="inventario-leche"),
    path("inventario/queso", views.inventario_queso, name="inventario-queso"),
    *router.urls,
]
