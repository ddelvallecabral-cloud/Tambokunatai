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

        self._precios_demo()
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
            self._ventas_demo(admin)
            self._egresos_demo(operador, admin, insumos)
        finally:
            terminar_contexto(token)

    def _precios_demo(self):
        """Tabla de precios inicial (Gs.). Solo si todavía no hay ninguno: después la maneja el Administrador."""
        from decimal import Decimal

        from apps.core.contexto import fijar_usuario, iniciar_contexto, terminar_contexto
        from apps.ventas.models import Precio

        if Precio.objects.exists():
            return
        token = iniciar_contexto()
        fijar_usuario(Usuario.objects.get(usuario="admin"))
        try:
            for producto, tipo, minimo, precio in (
                ("queso", "", "0", 40_000),             # precio base (minorista)
                ("queso", "mayorista", "0", 36_000),
                ("queso", "distribuidor", "0", 34_000),
                ("queso", "tienda_propia", "0", 40_000),
                ("queso", "", "20", 37_000),            # por volumen: desde 20 kg
                ("leche", "", "0", 3_500),
                ("leche", "", "100", 3_200),            # por volumen: desde 100 L
            ):
                Precio.objects.create(producto=producto, tipo_cliente=tipo, cantidad_minima=Decimal(minimo),
                                      precio_unitario=precio)
        finally:
            terminar_contexto(token)
        self.stdout.write("  tabla de precios inicial cargada")

    def _ventas_demo(self, admin):
        """Clientes de ejemplo y ventas de los últimos días: unas cobradas, otras a crédito y una vencida."""
        import datetime
        from decimal import Decimal

        from django.utils import timezone

        from apps.core.contexto import fijar_usuario
        from apps.ventas import servicios as ventas
        from apps.ventas.models import Cliente

        vendedor = Usuario.objects.get(usuario="ventas")
        fijar_usuario(admin)
        clientes = {c[0]: Cliente.objects.create(nombre=c[0], tipo=c[1], condicion_pago=c[2], telefono=c[3],
                                                 direccion=c[4]) for c in (
            ("Despensa San Roque", "minorista", "contado", "0981 456 120", "Ñemby, barrio San Roque"),
            ("Supermercado La Familia", "mayorista", "credito_15", "021 960 300", "San Lorenzo, Ruta 1"),
            ("Distribuidora Ñemby", "distribuidor", "credito_30", "0972 300 450", "Ñemby centro"),
            ("Puesto propio Mercado 4", "tienda_propia", "contado", "", "Asunción, Mercado 4"),
            ("Bar Doña Juana", "minorista", "credito_7", "0985 777 012", "Ñemby, ruta a Villeta"),
        )}
        fijar_usuario(vendedor)
        hoy = timezone.localdate()
        hechas = 0
        for dias, cliente, producto, cantidad, entregada, cobro in (
            (4, "Supermercado La Familia", "queso", "12", True, "todo"),
            (4, "Despensa San Roque", "queso", "3", True, "todo"),
            (3, "Distribuidora Ñemby", "queso", "15", True, "parte"),
            (3, "Despensa San Roque", "queso", "2", True, ""),       # contado sin cobrar: vencida
            (2, "Puesto propio Mercado 4", "queso", "6", True, "todo"),
            (2, "Despensa San Roque", "leche", "20", True, "todo"),
            (1, "Supermercado La Familia", "queso", "8", True, ""),
            (1, "Bar Doña Juana", "leche", "15", False, ""),
        ):
            fecha = hoy - datetime.timedelta(days=dias)
            try:
                venta, _ = ventas.registrar_venta(vendedor, cliente=clientes[cliente], producto=producto,
                                                  cantidad=Decimal(cantidad), fecha=fecha, entregada=entregada)
            except Exception as e:  # sin stock suficiente en la demo: se saltea
                self.stdout.write(f"  venta de demo salteada ({cliente}): {e}")
                continue
            if cobro:
                monto = venta.total if cobro == "todo" else venta.total // 2
                ventas.registrar_cobro(vendedor, venta.cuenta, monto=monto, fecha=fecha,
                                       medio="efectivo" if cobro == "todo" else "transferencia")
            hechas += 1
        self.stdout.write(f"  clientes de demo: {len(clientes)}, ventas de demo: {hechas}")

    def _egresos_demo(self, operador, admin, insumos):
        """Proveedores, dos compras (una a crédito) y gastos: chicos aprobados solos y dos que esperan al Administrador."""
        import datetime
        from decimal import Decimal

        from django.utils import timezone

        from apps.compras import servicios as compras
        from apps.compras.models import Proveedor
        from apps.core.contexto import fijar_usuario
        from apps.gastos import servicios as gastos

        fijar_usuario(admin)
        provs = {p[0]: Proveedor.objects.create(nombre=p[0], tipo=p[1], contacto=p[2], telefono=p[3], ruc=p[4]) for p in (
            ("Agroveterinaria El Rodeo", "sanidad", "Dr. Benítez", "0981 220 330", "80012345-6"),
            ("Lácteos Insumos S.A.", "insumos", "Marta Giménez", "021 555 410", "80098765-1"),
            ("Estación Ñemby", "combustible", "", "0972 101 202", ""),
            ("Electricista Ramón Ayala", "servicios", "Ramón Ayala", "0985 404 505", ""),
        )}
        hoy = timezone.localdate()
        compras.registrar_compra(admin, proveedor=provs["Lácteos Insumos S.A."], fecha=hoy - datetime.timedelta(days=6),
                                 factura="001-001-0004521", condicion="credito_30", items=[
                                     {"insumo": insumos["CUAJO"], "cantidad": Decimal("1000"), "precio_unitario": 85, "lote_proveedor": "CJ-2702"},
                                     {"insumo": insumos["BOLSA"], "cantidad": Decimal("500"), "precio_unitario": 650},
                                 ])
        compras.registrar_compra(admin, proveedor=provs["Lácteos Insumos S.A."], fecha=hoy - datetime.timedelta(days=2),
                                 factura="001-001-0004602", condicion="contado", pagada=True, items=[
                                     {"insumo": insumos["SAL"], "cantidad": Decimal("25"), "precio_unitario": 4500},
                                 ])
        for usuario, dias, cat, centro, monto, desc, prov in (
            (operador, 5, "combustible", "produccion_leche", 180_000, "Gasoil para el generador del tambo", "Estación Ñemby"),
            (operador, 4, "sanidad", "produccion_leche", 95_000, "Antiparasitario para 6 terneros", "Agroveterinaria El Rodeo"),
            (operador, 2, "mantenimiento", "elaboracion_queso", 1_250_000, "Cambio del motor de la tina de cuajado", "Electricista Ramón Ayala"),
            (operador, 1, "alimentacion", "produccion_leche", 2_400_000, "Balanceado lechero, 40 bolsas", None),
            (admin, 3, "honorarios", "administracion", 900_000, "Honorarios del contador, noviembre", None),
        ):
            fijar_usuario(usuario)
            gastos.registrar_gasto(usuario, fecha=hoy - datetime.timedelta(days=dias), categoria=cat, centro_costo=centro,
                                   monto=monto, descripcion=desc, proveedor=provs.get(prov) if prov else None)
        fijar_usuario(admin)
        self.stdout.write(f"  egresos de demo: {len(provs)} proveedores, 2 compras, 5 gastos")

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
