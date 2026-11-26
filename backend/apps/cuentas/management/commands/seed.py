"""Carga inicial: establecimiento, parámetros y tres usuarios de prueba (uno por rol).

Es idempotente: se puede correr varias veces sin duplicar nada.
Las claves de prueba se pueden cambiar con variables de entorno SEED_CLAVE_*.
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Configuracion, Establecimiento
from apps.cuentas.catalogo import ADMIN, OPERADOR, VENTAS
from apps.cuentas.models import Rol, Usuario, UsuarioRol
from apps.cuentas.servicios import sincronizar_roles_y_permisos

USUARIOS_DEMO = [
    ("admin", "Dueño (Administrador)", ADMIN, "SEED_CLAVE_ADMIN", "Tambo.Admin2026"),
    ("operador", "Tambero de prueba", OPERADOR, "SEED_CLAVE_OPERADOR", "Tambo.Operador2026"),
    ("ventas", "Vendedor de prueba", VENTAS, "SEED_CLAVE_VENTAS", "Tambo.Ventas2026"),
]

CONFIGURACION_DEMO = [
    ("moneda", "PYG", "Moneda de trabajo (Guaraníes, sin decimales)"),
    ("zona_horaria", "America/Asuncion", "Zona horaria del establecimiento"),
    ("gastos.presupuesto_mensual_temporada_baja", 2_000_000, "Gasto mensual de referencia en temporada baja (Gs.)"),
    ("gastos.presupuesto_mensual_temporada_alta", 4_000_000, "Gasto mensual de referencia en temporada alta (Gs.)"),
    ("ventas.condicion_por_defecto", "contado", "Las ventas de queso son al contado por ahora"),
    ("queso.precio_lista_kg", 40_000, "Precio de lista del queso Paraguay por kg (Gs.)"),
    ("ordene.sesiones", ["mañana", "tarde"], "Sesiones de ordeñe por día"),
]


class Command(BaseCommand):
    help = "Crea el establecimiento, parámetros iniciales y usuarios de prueba (admin, operador, ventas)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        sincronizar_roles_y_permisos()

        establecimiento, _ = Establecimiento.objects.get_or_create(
            nombre="Tambo Lechero Kuñatai",
            defaults={"direccion": "Barrio Caaguazú, Ñemby, Paraguay"},
        )
        for clave, valor, descripcion in CONFIGURACION_DEMO:
            Configuracion.objects.get_or_create(
                establecimiento=establecimiento, clave=clave,
                defaults={"valor": valor, "descripcion": descripcion},
            )

        for usuario, nombre, rol_codigo, variable, clave_defecto in USUARIOS_DEMO:
            user = Usuario.objects.filter(usuario=usuario).first()
            if user is None:
                user = Usuario.objects.create_user(
                    usuario, os.environ.get(variable, clave_defecto), nombre=nombre,
                    is_staff=(rol_codigo == ADMIN), is_superuser=(rol_codigo == ADMIN),
                )
                self.stdout.write(f"  usuario creado: {usuario}")
            UsuarioRol.objects.get_or_create(
                usuario=user, rol=Rol.objects.get(codigo=rol_codigo), establecimiento=establecimiento
            )

        self._demo(establecimiento)
        self.stdout.write(self.style.SUCCESS("Seed listo."))

    def _demo(self, establecimiento):
        """Datos de demostración: rodeo, 20 días de ordeñe por vaca, insumos y lotes de queso.
        Solo se cargan si la base todavía no tiene lotes de leche."""
        from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
        from apps.leche.models import LoteLeche

        if LoteLeche.objects.exists():
            return
        operador = Usuario.objects.get(usuario="operador")
        admin = Usuario.objects.get(usuario="admin")
        token = iniciar_contexto()
        fijar_usuario(operador)
        try:
            vacas = self._rodeo_demo()
            lotes = self._leche_demo(establecimiento, operador, vacas)
            insumos = self._insumos_demo(admin)
            self._queso_demo(operador, admin, lotes, insumos)
        finally:
            terminar_contexto(token)

    def _rodeo_demo(self):
        from apps.rodeo.models import Animal

        plantel = [
            ("101", "Pintada", "Holando", "en_ordene"), ("102", "Mora", "Holando", "en_ordene"),
            ("103", "Negra", "Holando", "en_ordene"), ("104", "Estrella", "Jersey", "en_ordene"),
            ("105", "Canela", "Jersey", "en_ordene"), ("106", "Blanca", "Holando", "en_ordene"),
            ("107", "Lucera", "Girolando", "en_ordene"), ("108", "Paloma", "Girolando", "en_ordene"),
            ("109", "Manchita", "Holando", "en_ordene"), ("110", "Rubia", "Jersey", "en_ordene"),
            ("111", "Morocha", "Holando", "seca"), ("112", "Chiquita", "Girolando", "en_recria"),
        ]
        vacas = []
        for caravana, nombre, raza, situacion in plantel:
            animal, _ = Animal.objects.get_or_create(
                caravana=caravana,
                defaults={"nombre": nombre, "raza": raza, "situacion": situacion,
                          "categoria": "vaquillona" if situacion == "en_recria" else "vaca"},
            )
            vacas.append(animal)
        self.stdout.write(f"  rodeo de demo: {len(vacas)} animales")
        return [v for v in vacas if v.situacion == "en_ordene"]

    def _leche_demo(self, establecimiento, operador, vacas):
        """20 días de ordeñe por vaca (sin hoy). Ayer queda bajo para que se vea la alerta del panel.
        La 105 viene bajando y la 108 subiendo, para que se vea la tendencia."""
        import datetime
        import random
        from decimal import Decimal

        from django.utils import timezone

        from apps.leche import servicios
        from apps.rodeo import servicios as rodeo

        azar = random.Random(42)
        hoy = timezone.localdate()
        base = {v.caravana: Decimal(azar.choice([14, 15, 15, 16, 16, 17])) for v in vacas}
        lotes = {}
        for dias_atras in range(20, 0, -1):
            fecha = hoy - datetime.timedelta(days=dias_atras)
            for ordene, factor in (("manana", Decimal("1")), ("tarde", Decimal("0.82"))):
                items = []
                for v in vacas:
                    litros = base[v.caravana] * factor + Decimal(azar.randint(-10, 10)) / 10
                    if v.caravana == "105" and dias_atras <= 7:
                        litros -= 4
                    if v.caravana == "108" and dias_atras <= 7:
                        litros += 2
                    if dias_atras == 1:
                        litros *= Decimal("0.8")
                    items.append({"animal": v, "litros": litros.quantize(Decimal("0.1"))})
                r = rodeo.registrar_ordene(operador, fecha=fecha, ordene=ordene, items=items)
                lote = r["lote"]
                if lote.establecimiento_id is None:
                    LoteLeche = type(lote)
                    LoteLeche.objects.filter(pk=lote.pk).update(establecimiento=establecimiento)
                venta = Decimal(azar.choice([0, 10, 15, 20]))
                if venta:
                    servicios.asignar_destino(operador, lote, tipo="venta", litros=venta)
                if dias_atras > 1:
                    servicios.asignar_destino(operador, lote, tipo="elaboracion_queso", litros=lote.litros - venta)
                    servicios.cerrar_lote(operador, lote)
                lotes[(dias_atras, ordene)] = lote
        self.stdout.write("  historial de ordeñe por vaca de demo: 20 días")
        return lotes

    def _insumos_demo(self, admin):
        from decimal import Decimal

        from apps.inventario import servicios as inventario
        from apps.inventario.models import Insumo

        catalogo = [
            ("CUAJO", "Cuajo líquido", "cuajo", "ml", 300, 3000, "CJ-2611"),
            ("CACL2", "Cloruro de calcio", "aditivo", "ml", 200, 2000, "CC-1102"),
            ("SAL", "Sal fina", "sal", "kg", 5, 25, ""),
            ("FERM", "Fermento láctico", "cultivo", "g", 50, 250, "FL-0925"),
            ("BOLSA", "Bolsa al vacío 1 kg", "envase", "unidad", 100, 400, ""),
        ]
        insumos = {}
        for codigo, nombre, categoria, unidad, minimo, inicial, lote_prov in catalogo:
            insumo, creado = Insumo.objects.get_or_create(
                codigo=codigo, defaults={"nombre": nombre, "categoria": categoria, "unidad": unidad,
                                         "stock_minimo": Decimal(minimo)})
            if creado:
                inventario.entrada(admin, insumo, Decimal(inicial), lote_proveedor=lote_prov)
            insumos[codigo] = insumo
        self.stdout.write(f"  insumos de demo: {len(insumos)}")
        return insumos

    def _queso_demo(self, operador, admin, lotes, insumos):
        """Un lote de queso por día con la leche de la tarde anterior y la mañana.
        Los de hace 3 días o más quedan aprobados; el de anteayer, pendiente y con rendimiento bajo."""
        from decimal import Decimal

        from apps.core.contexto import fijar_usuario
        from apps.queso import servicios as queso

        hechos = 0
        for dias_atras in range(7, 1, -1):
            origenes = [lotes[(dias_atras + 1, "tarde")], lotes[(dias_atras, "manana")]]
            disponibles = [(l, queso.leche_disponible(l)["destinado_a_queso"]) for l in origenes]
            origenes = [{"lote_leche": l, "litros": x} for l, x in disponibles if x > 0]
            if not origenes:
                continue
            litros = sum((o["litros"] for o in origenes), Decimal("0"))
            fijar_usuario(operador)
            fecha = origenes[-1]["lote_leche"].fecha
            consumo = [("CUAJO", litros * Decimal("0.25")), ("CACL2", litros * Decimal("0.2")),
                       ("SAL", Decimal("0.6")), ("FERM", Decimal("5"))]
            lote, _ = queso.iniciar_lote(
                operador, fecha=fecha, origenes=origenes,
                insumos=[{"insumo": insumos[c], "cantidad": q.quantize(Decimal("1"))} for c, q in consumo],
            )
            rendimiento = Decimal("12.1") if dias_atras == 2 else Decimal("9.2") + Decimal(dias_atras % 3) / 10
            kg = (litros / rendimiento).quantize(Decimal("0.1"))
            consumos = [{"insumo": insumos[c], "cantidad": q.quantize(Decimal("1"))} for c, q in consumo]
            consumos.append({"insumo": insumos["BOLSA"], "cantidad": kg.quantize(Decimal("1"))})
            queso.cerrar_lote(operador, lote, kg_obtenidos=kg, merma_kg=Decimal("0.3"), consumos=consumos)
            if dias_atras >= 3:
                fijar_usuario(admin)
                queso.aprobar_lote(admin, lote)
            hechos += 1
        fijar_usuario(operador)
        self.stdout.write(f"  lotes de queso de demo: {hechos}")
