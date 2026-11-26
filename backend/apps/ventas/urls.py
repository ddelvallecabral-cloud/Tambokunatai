from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("clientes", views.ClienteViewSet, basename="cliente")
router.register("precios", views.PrecioViewSet, basename="precio")
router.register("ventas", views.VentaViewSet, basename="venta")
router.register("cuentas-por-cobrar", views.CuentaViewSet, basename="cuenta-por-cobrar")

urlpatterns = [path("cuentas-por-cobrar-resumen", views.resumen_cuentas, name="cuentas-resumen"), *router.urls]
