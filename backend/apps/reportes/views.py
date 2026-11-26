import datetime

from django.http import Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.core.contexto import fijar_usuario
from apps.core.vistas import fecha_param
from apps.cuentas.permisos import requiere_permiso

from . import alertas, exportar, servicios

FINANCIEROS = "reportes.financieros"


def requiere_alguno(*codigos):
    """Pasa si el usuario tiene al menos uno de los permisos."""
    class TieneAlguno(BasePermission):
        message = "No tenés permiso para esta acción."

        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and any(u.tiene_permiso(c) for c in codigos))

    return TieneAlguno
MAX_DIAS = 3 * 366


def _periodo(request, por_defecto="mes"):
    """desde/hasta del query string; por defecto, el mes en curso."""
    hoy = servicios.hoy()
    desde = fecha_param(request.query_params.get("desde"), "desde")
    hasta = fecha_param(request.query_params.get("hasta"), "hasta") or hoy
    if desde is None:
        desde = hasta.replace(day=1) if por_defecto == "mes" else hasta.replace(month=1, day=1)
    if desde > hasta:
        raise ValidationError({"desde": "La fecha desde no puede ser posterior a hasta."})
    if (hasta - desde).days > MAX_DIAS:
        raise ValidationError({"desde": "El período no puede superar los 3 años."})
    return desde, hasta


@api_view(["GET"])
@permission_classes([requiere_alguno("reportes.operativos", FINANCIEROS)])
def tablero(request):
    """Indicadores del día y del mes. La parte de plata solo para quien tiene reportes financieros."""
    fecha = fecha_param(request.query_params.get("fecha")) or servicios.hoy()
    financiero = request.user.tiene_permiso(FINANCIEROS)
    datos = {"operativo": servicios.tablero_operativo(fecha),
             "alertas": servicios.calcular_alertas(fecha, financieras=financiero)}
    if financiero:
        datos["financiero"] = servicios.tablero_financiero(fecha)
    if request.user.tiene_permiso("gastos.gasto.aprobar"):
        datos["pendientes"] = servicios.pendientes_control()
    return Response(datos)


@api_view(["GET"])
@permission_classes([requiere_permiso(FINANCIEROS)])
def estado_resultados(request):
    return Response(servicios.estado_resultados(*_periodo(request)))


@api_view(["GET"])
@permission_classes([requiere_permiso(FINANCIEROS)])
def flujo_caja(request):
    agrupar = request.query_params.get("agrupar", "dia")
    if agrupar not in ("dia", "mes"):
        raise ValidationError({"agrupar": "Usá dia o mes."})
    return Response(servicios.flujo_caja(*_periodo(request, "mes" if agrupar == "dia" else "anio"), agrupar))


@api_view(["GET"])
@permission_classes([requiere_permiso(FINANCIEROS)])
def rentabilidad_lotes(request):
    return Response(servicios.rentabilidad_lotes(*_periodo(request)))


@api_view(["GET"])
@permission_classes([requiere_permiso(FINANCIEROS)])
def rentabilidad_productos(request):
    return Response(servicios.rentabilidad_productos(*_periodo(request)))


@api_view(["GET"])
@permission_classes([requiere_alguno("reportes.ventas_propias", FINANCIEROS)])
def mis_ventas(request):
    """Ventas y cobros del usuario que consulta: cada vendedor ve solo lo suyo."""
    desde, hasta = _periodo(request)
    return Response(servicios.mis_ventas(request.user, desde, hasta))


@api_view(["GET"])
@permission_classes([requiere_permiso("auditoria.ver")])
def historial_aprobaciones(request):
    desde, hasta = _periodo(request)
    p = request.query_params
    return Response(servicios.historial_aprobaciones(desde, hasta, p.get("usuario") or None, p.get("entidad") or None))


PERMISO_EXPORTAR = {"aprobaciones": "auditoria.ver"}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportar_reporte(request, nombre, formato):
    if nombre not in exportar.REPORTES or formato not in ("pdf", "xlsx"):
        raise Http404
    permiso = PERMISO_EXPORTAR.get(nombre, FINANCIEROS)
    if not request.user.tiene_permiso(permiso):
        return Response({"detail": "No tenés permiso para esta acción."}, status=403)
    desde, hasta = _periodo(request, "anio" if nombre == "flujo-caja-mensual" else "mes")
    return exportar.respuesta(nombre, desde, hasta, formato)


@api_view(["GET"])
@permission_classes([requiere_permiso("auditoria.ver")])
def registros_editados(request):
    p = request.query_params
    return Response(servicios.registros_editados(fecha_param(p.get("desde"), "desde"), fecha_param(p.get("hasta"), "hasta"),
                                                 solo_sin_revisar=p.get("sin_revisar") == "1"))


@api_view(["POST"])
@permission_classes([requiere_permiso("auditoria.ver")])
def revisar_registro(request, auditoria_id):
    fijar_usuario(request.user)
    servicios.marcar_revisado(request.user, int(auditoria_id), str(request.data.get("nota", ""))[:255])
    return Response({"ok": True})


@api_view(["GET", "PUT"])
@permission_classes([requiere_alguno("reportes.operativos", FINANCIEROS, "configuracion.gestionar")])
def configuracion_alertas(request):
    if request.method == "PUT":
        if not request.user.tiene_permiso("configuracion.gestionar"):
            return Response({"detail": "Solo el Administrador cambia las alertas."}, status=403)
        fijar_usuario(request.user)
        return Response(alertas.guardar(request.user, request.data))
    return Response(alertas.leer())


@api_view(["GET"])
@permission_classes([requiere_alguno("reportes.operativos", FINANCIEROS)])
def lista_alertas(request):
    fecha = fecha_param(request.query_params.get("fecha")) or servicios.hoy()
    return Response(servicios.calcular_alertas(fecha, financieras=request.user.tiene_permiso(FINANCIEROS)))
