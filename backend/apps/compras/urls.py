from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("proveedores", views.ProveedorViewSet, basename="proveedor")
router.register("compras", views.CompraViewSet, basename="compra")
router.register("cuentas-por-pagar", views.CuentaPagarViewSet, basename="cuenta-por-pagar")

urlpatterns = [path("cuentas-por-pagar-resumen", views.resumen_cuentas, name="cuentas-pagar-resumen"), *router.urls]
