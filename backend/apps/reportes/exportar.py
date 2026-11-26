"""Exporta los reportes a Excel (.xlsx) y PDF. Cada reporte se describe como secciones de tabla
y los dos formatos se arman a partir de esa misma descripción, así muestran exactamente lo mismo."""

import datetime
import io
from decimal import Decimal

from django.http import HttpResponse

from apps.gastos.models import Categoria, CentroCosto

from . import servicios

NOMBRE_CATEGORIA = dict(Categoria.choices)
NOMBRE_CENTRO = dict(CentroCosto.choices)


def _fecha(d):
    if isinstance(d, datetime.datetime):
        return d.astimezone().strftime("%d/%m/%Y %H:%M")
    return d.strftime("%d/%m/%Y") if d else ""


def _texto(valor, tipo):
    if valor is None or valor == "":
        return "—" if tipo != "texto" else ""
    if tipo == "gs":
        return f"Gs. {int(valor):,}".replace(",", ".")
    if tipo == "num":
        texto = f"{Decimal(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return texto.removesuffix(",00")
    if tipo == "pct":
        return f"{valor} %".replace(".", ",")
    if tipo == "fecha":
        return _fecha(valor)
    if tipo == "mes":
        return valor.strftime("%m/%Y")
    return str(valor)


# --- Definición de cada reporte ---------------------------------------------------------------

def _estado_resultados(desde, hasta):
    r = servicios.estado_resultados(desde, hasta)
    filas = [{"concepto": f"Ventas de {i['concepto'].lower()}", "monto": i["monto"]} for i in r["ingresos"]]
    filas.append({"concepto": "Total ingresos", "monto": r["total_ingresos"], "_negrita": True})
    for g in r["gastos_por_categoria"]:
        filas.append({"concepto": f"Gastos: {NOMBRE_CATEGORIA.get(g['categoria'], g['categoria'])}", "monto": -g["total"]})
    filas.append({"concepto": "Compras de insumos", "monto": -r["compras_insumos"]})
    filas.append({"concepto": "Total egresos", "monto": -r["total_egresos"], "_negrita": True})
    filas.append({"concepto": "Resultado del período", "monto": r["resultado"], "_negrita": True})
    centros = [{"centro": NOMBRE_CENTRO.get(c["centro_costo"], c["centro_costo"]), "total": c["total"], "cantidad": c["cantidad"]}
               for c in r["gastos_por_centro"]]
    secciones = [
        {"titulo": "Estado de resultados", "columnas": [("concepto", "Concepto", "texto"), ("monto", "Monto", "gs")], "filas": filas},
        {"titulo": "Gastos por centro de costo", "columnas": [("centro", "Centro de costo", "texto"), ("cantidad", "Gastos", "texto"),
                                                               ("total", "Total", "gs")], "filas": centros},
    ]
    notas = ["Ingresos: ventas no anuladas por fecha de venta. Gastos: solo aprobados. Compras de insumos: en el mes en que se compran."]
    if r["gastos_pendientes"]["cantidad"]:
        notas.append(f"No incluye {r['gastos_pendientes']['cantidad']} gastos pendientes de aprobación por "
                     f"{_texto(r['gastos_pendientes']['total'], 'gs')}.")
    return "Estado de resultados", secciones, notas


def _flujo(desde, hasta, agrupar="dia"):
    r = servicios.flujo_caja(desde, hasta, agrupar)
    columnas = [("periodo", "Día" if agrupar == "dia" else "Mes", "fecha" if agrupar == "dia" else "mes"),
                ("cobros", "Cobros", "gs"), ("pagos_proveedores", "Pagos a proveedores", "gs"), ("gastos", "Gastos", "gs"),
                ("neto", "Neto", "gs"), ("acumulado", "Acumulado", "gs")]
    filas = r["filas"] + [{"periodo": None, **r["totales"], "acumulado": None, "_negrita": True, "_etiqueta": "Total"}]
    titulo = "Flujo de caja diario" if agrupar == "dia" else "Flujo de caja mensual"
    return titulo, [{"titulo": titulo, "columnas": columnas, "filas": filas}], [
        "Entradas: cobros registrados. Salidas: pagos a proveedores y gastos aprobados (tomados como pagados en su fecha)."]


def _lotes(desde, hasta):
    r = servicios.rentabilidad_lotes(desde, hasta)
    columnas = [("codigo", "Lote", "texto"), ("fecha", "Fecha", "fecha"), ("litros", "Litros", "num"), ("kg", "Kg", "num"),
                ("rendimiento", "L/kg", "num"), ("costo_leche", "Leche", "gs"), ("costo_insumos", "Insumos", "gs"),
                ("costo_elaboracion", "Elaboración", "gs"), ("costo_total", "Costo total", "gs"), ("costo_kg", "Costo/kg", "gs"),
                ("kg_vendidos", "Kg vendidos", "num"), ("ingresos", "Ingresos", "gs"), ("resultado", "Resultado", "gs")]
    filas = r["lotes"] + [{**r["totales"], "codigo": "Total", "_negrita": True}]
    notas = ["Costo del lote = leche (al costo por litro del mes) + insumos consumidos (precio promedio de compra) + "
             "su parte de los gastos de elaboración del mes. Ingresos: ventas de ese lote hasta hoy."]
    sin_precio = sorted({n for l in r["lotes"] for n in l["insumos_sin_precio"]})
    if sin_precio:
        notas.append("Sin precio de compra (no suman costo): " + ", ".join(sin_precio) + ".")
    return "Rentabilidad por lote de queso", [{"titulo": "Lotes", "columnas": columnas, "filas": filas}], notas


def _productos(desde, hasta):
    r = servicios.rentabilidad_productos(desde, hasta)
    columnas = [("nombre", "Producto", "texto"), ("cantidad", "Cantidad", "num"), ("unidad", "", "texto"),
                ("ingresos", "Ingresos", "gs"), ("costo", "Costo de lo vendido", "gs"), ("margen", "Margen bruto", "gs"),
                ("margen_pct", "Margen %", "pct")]
    filas = r["productos"] + [{"nombre": "Total", **r["total"], "_negrita": True}]
    meses = [{"mes": m["mes"], "gastos": m["gastos"], "litros": m["litros"], "por_litro": m["por_litro"]}
             for m in r["costo_litro_por_mes"]]
    return "Rentabilidad por producto", [
        {"titulo": "Margen bruto por producto", "columnas": columnas, "filas": filas},
        {"titulo": "Costo de la leche por mes", "columnas": [("mes", "Mes", "mes"), ("gastos", "Gastos producción", "gs"),
                                                            ("litros", "Litros", "num"), ("por_litro", "Costo por litro", "gs")],
         "filas": meses},
    ], [f"Gastos de administración del período (no se reparten entre productos): {_texto(r['gastos_administracion'], 'gs')}."]


def _aprobaciones(desde, hasta):
    filas = servicios.historial_aprobaciones(desde, hasta)
    columnas = [("fecha", "Fecha", "fecha"), ("usuario", "Quién", "texto"), ("accion_nombre", "Acción", "texto"),
                ("entidad_nombre", "Qué", "texto"), ("registro", "Registro", "texto"), ("motivo", "Comentario", "texto")]
    return "Historial de aprobaciones", [{"titulo": "Aprobaciones y rechazos", "columnas": columnas, "filas": filas}], []


REPORTES = {
    "estado-resultados": _estado_resultados,
    "flujo-caja": _flujo,
    "flujo-caja-mensual": lambda d, h: _flujo(d, h, "mes"),
    "rentabilidad-lotes": _lotes,
    "rentabilidad-productos": _productos,
    "aprobaciones": _aprobaciones,
}


# --- Formatos ----------------------------------------------------------------------------------

def _valor_celda(fila, clave, tipo):
    if clave in ("periodo", "codigo", "concepto", "nombre") and fila.get("_etiqueta"):
        return fila["_etiqueta"]
    v = fila.get(clave)
    if v is None:
        return None
    if tipo in ("gs",):
        return int(v)
    if tipo in ("num", "pct"):
        return float(v)
    if tipo == "fecha":
        if isinstance(v, datetime.datetime):
            return v.astimezone().replace(tzinfo=None)
        return v
    if tipo == "mes":
        return v.strftime("%m/%Y")
    return str(v)


def a_excel(titulo, subtitulo, secciones, notas) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo[:31]
    hoja.append([titulo])
    hoja["A1"].font = Font(bold=True, size=14)
    hoja.append([subtitulo])
    fila = 3
    anchos = {}
    for s in secciones:
        fila += 1
        hoja.cell(row=fila, column=1, value=s["titulo"]).font = Font(bold=True, size=12)
        fila += 1
        for i, (_, nombre, _) in enumerate(s["columnas"], start=1):
            c = hoja.cell(row=fila, column=i, value=nombre)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F5D2F")
            anchos[i] = max(anchos.get(i, 8), len(nombre) + 2)
        for f in s["filas"]:
            fila += 1
            for i, (clave, _, tipo) in enumerate(s["columnas"], start=1):
                v = _valor_celda(f, clave, tipo)
                c = hoja.cell(row=fila, column=i, value=v)
                if tipo == "gs":
                    c.number_format = '"Gs." #,##0;-"Gs." #,##0'
                elif tipo == "num":
                    c.number_format = "#,##0.##"
                elif tipo == "fecha":
                    c.number_format = "dd/mm/yyyy hh:mm" if isinstance(v, datetime.datetime) else "dd/mm/yyyy"
                if f.get("_negrita"):
                    c.font = Font(bold=True)
                anchos[i] = max(anchos.get(i, 8), min(len(_texto(f.get(clave), tipo)) + 2, 60))
        fila += 1
    for n in notas:
        fila += 1
        hoja.cell(row=fila, column=1, value=n).alignment = Alignment(wrap_text=False)
    for i, ancho in anchos.items():
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def a_pdf(titulo, subtitulo, secciones, notas) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ancho_max = max(len(s["columnas"]) for s in secciones)
    pagina = landscape(A4) if ancho_max > 6 else A4
    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=pagina, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=titulo)
    estilos = getSampleStyleSheet()
    chico = estilos["BodyText"].clone("chico", fontSize=7.5, leading=9)
    partes = [Paragraph(titulo, estilos["Title"]), Paragraph(subtitulo, estilos["Normal"]), Spacer(1, 0.4 * cm)]
    for s in secciones:
        partes.append(Paragraph(s["titulo"], estilos["Heading3"]))
        datos = [[Paragraph(f"<b>{n}</b>", chico) for _, n, _ in s["columnas"]]]
        negritas = []
        for idx, f in enumerate(s["filas"], start=1):
            celdas = []
            for clave, _, tipo in s["columnas"]:
                v = f["_etiqueta"] if clave in ("periodo", "codigo", "concepto", "nombre") and f.get("_etiqueta") else _texto(f.get(clave), tipo)
                celdas.append(Paragraph(str(v), chico))
            datos.append(celdas)
            if f.get("_negrita"):
                negritas.append(idx)
        if len(datos) == 1:
            partes.append(Paragraph("Sin datos en el período.", estilos["Normal"]))
            continue
        tabla = Table(datos, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5D2F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for i, (_, _, tipo) in enumerate(s["columnas"]):
            if tipo in ("gs", "num", "pct"):
                estilo.append(("ALIGN", (i, 1), (i, -1), "RIGHT"))
        for n in negritas:
            estilo.append(("BACKGROUND", (0, n), (-1, n), colors.HexColor("#EEF3EA")))
        tabla.setStyle(TableStyle(estilo))
        partes += [tabla, Spacer(1, 0.4 * cm)]
    for n in notas:
        partes.append(Paragraph(n, chico))
    doc.build(partes)
    return salida.getvalue()


def respuesta(nombre: str, desde, hasta, formato: str) -> HttpResponse:
    titulo, secciones, notas = REPORTES[nombre](desde, hasta)
    subtitulo = f"Del {_fecha(desde)} al {_fecha(hasta)} · generado el {_fecha(datetime.datetime.now().astimezone())}"
    archivo = f"{nombre}_{desde:%Y%m%d}_{hasta:%Y%m%d}"
    if formato == "xlsx":
        contenido = a_excel(titulo, subtitulo, secciones, notas)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        contenido = a_pdf(titulo, subtitulo, secciones, notas)
        tipo = "application/pdf"
    r = HttpResponse(contenido, content_type=tipo)
    r["Content-Disposition"] = f'attachment; filename="{archivo}.{formato}"'
    r["Cache-Control"] = "private, no-store"
    return r
