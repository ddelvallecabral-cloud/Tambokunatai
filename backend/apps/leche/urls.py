from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("lotes-leche", views.LoteLecheViewSet, basename="lote-leche")

urlpatterns = [path("leche/tablero", views.tablero, name="leche-tablero"), *router.urls]
