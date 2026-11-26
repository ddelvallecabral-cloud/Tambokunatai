from django.urls import path

from . import views

urlpatterns = [
    path("tablero", views.tablero, name="tablero"),
    path("reportes/estado-resultados", views.estado_resultados),
    path("reportes/flujo-caja", views.flujo_caja),
    path("reportes/rentabilidad-lotes", views.rentabilidad_lotes),
    path("reportes/rentabilidad-productos", views.rentabilidad_productos),
    path("reportes/aprobaciones", views.historial_aprobaciones),
    path("reportes/<str:nombre>.<str:formato>", views.exportar_reporte),
    path("control/registros-editados", views.registros_editados),
    path("control/registros-editados/<int:auditoria_id>/revisar", views.revisar_registro),
    path("alertas", views.lista_alertas),
    path("alertas/configuracion", views.configuracion_alertas),
]
