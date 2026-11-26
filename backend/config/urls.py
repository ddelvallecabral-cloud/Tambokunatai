from django.contrib import admin
from django.urls import include, path

from apps.core.views import salud

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/salud", salud),
    path("api/v1/", include("apps.cuentas.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.leche.urls")),
    path("api/v1/", include("apps.rodeo.urls")),
    path("api/v1/", include("apps.inventario.urls")),
    path("api/v1/", include("apps.queso.urls")),
    path("api/v1/", include("apps.ventas.urls")),
    path("api/v1/", include("apps.compras.urls")),
    path("api/v1/", include("apps.gastos.urls")),
    path("api/v1/", include("apps.reportes.urls")),
]
