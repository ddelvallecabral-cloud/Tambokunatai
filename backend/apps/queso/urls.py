from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("lotes-queso", views.LoteQuesoViewSet, basename="lote-queso")

urlpatterns = [
    path("queso/leche-disponible", views.leche_disponible, name="queso-leche-disponible"),
    path("queso/resumen", views.resumen, name="queso-resumen"),
    path("lotes-leche/<uuid:pk>/quesos", views.trazabilidad_lote_leche, name="lote-leche-quesos"),
    *router.urls,
]
