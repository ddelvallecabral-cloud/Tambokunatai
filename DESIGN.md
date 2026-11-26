# Diseño técnico

El diseño completo aprobado en la Fase 0 (stack, modelo de datos de 37 tablas, mapa de endpoints,
flujos, roles y permisos, auditoría, trazabilidad y plan de fases) está en el documento
**Diseño técnico ERP Tambo Kuñatai**: <https://claude.ai/artifact/YBPMTiUCoE6Mbyys1uucDM>

## Decisiones confirmadas por el dueño (26/11/2026)

- **Gastos:** el gasto mensual varía con la temporada, aprox. Gs. 2.000.000 (baja) a Gs. 4.000.000 (alta).
  El umbral de aprobación es configurable, no fijo en el código. Cargado como parámetro en `configuracion`.
- **Ordeñe:** se registra por vaca y por sesión (mañana / tarde) para seguir si la producción se
  mantiene, baja o sube.
- **Clientes:** principalmente particulares, no acopiadores.
- **Modo sin conexión:** necesario; la señal en el campo falla.
- **Ventas de queso:** al contado por ahora; a crédito más adelante.

## Plan de fases

1. Setup, base de datos, autenticación, usuarios, roles, permisos y auditoría base. ← **hecho**
2. Producción de leche: lotes por sesión de ordeñe, destinos con saldo, correcciones con aprobación,
   panel con alertas y carga sin conexión. ← **hecho**
3. Rodeo y ordeñe por vaca, pantalla de usuarios; inventario, insumos, compras y lotes de queso con aprobación
   (a repartir según prioridad del dueño).
4. Clientes, ventas, entregas, cuentas por cobrar y cobros.
5. Gastos, bandeja de aprobaciones, cierre de mes.
6. Reportes, tablero del dueño, pantalla de auditoría e importación de planillas.
7. Integración SIFEN (opcional).

## Decisiones técnicas de la Fase 1

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Framework | Django 5.2 LTS + DRF (no FastAPI) | Migraciones, permisos y panel de respaldo incluidos; soporte hasta 2028 |
| Migraciones | Las de Django (equivalente a Alembic) | Vienen integradas con el ORM |
| Contraseñas | Argon2 + validadores (mín. 8, no comunes, no solo números) | Recomendación actual de OWASP |
| Sesión | JWT de acceso de 15 min en memoria + refresh de 7 días en cookie httpOnly, rotado en cada uso y con lista negra | El JavaScript no puede robar el refresh; un refresh usado o cerrado no sirve más |
| Login | Limitado a 30 intentos por minuto por IP | Freno a ataques de fuerza bruta. Hasta poner un proxy HTTPS (Caddy) delante en el despliegue, el backend ve la IP del contenedor del frontend: el límite es compartido y la auditoría registra esa IP en lugar de la del celular |
| Registro | Solo el Administrador crea usuarios (`POST /usuarios`), no hay registro público | Es un sistema interno |
| Permisos | Granulares (`modulo.entidad.accion`); roles = paquetes de permisos definidos en `catalogo.py` | Se puede crear un rol nuevo sin tocar código de las vistas |
| Menú | El backend devuelve los módulos visibles para cada usuario | El frontend no decide permisos; un ítem no permitido nunca llega |
| Auditoría | Tabla de solo inserción con cadena de hashes SHA-256; triggers de PostgreSQL bloquean UPDATE, DELETE y TRUNCATE | Nadie puede alterarla desde el sistema; una edición puntual hecha directo en la base se detecta con `/auditoria/verificar`. (Alguien con control total del servidor podría recalcular toda la cadena: para eso, en una fase posterior, se guarda una copia diaria del último hash fuera del servidor) |
| Usuario en la auditoría | Contexto por petición (ContextVar) completado por el middleware y la autenticación JWT | Los modelos saben quién actúa sin pasar el usuario a mano |
| Frontend → backend | Next.js reenvía `/api/*` al backend | Mismo origen: la cookie funciona sin CORS |
| Nombres de columnas | Los del pedido de Fase 1 (`fecha_creacion`, `modificado_por`…) | Prevalecen sobre los nombres del documento de diseño (`creado_en`, `actualizado_por`) |

## Decisiones de la Fase 2 (leche)

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Unidad de registro | Un lote por fecha y ordeñe (mañana / tarde); no se pueden cargar dos para la misma sesión | Así lo pidió la Fase 2 y evita duplicados. El ordeñe por vaca queda para la fase de rodeo |
| Destino | Se elige al cargar (queso, venta, descarte o pendiente) y se puede repartir después: cada asignación descuenta del saldo disponible, que nunca puede quedar negativo | Interpreté "si destino = queso y venta, calcular saldo" como repartir los litros de un lote entre varios destinos |
| Destino del lote | Calculado: pendiente, el único destino, o "repartido" | Una sola fuente de verdad: las asignaciones |
| Corrección de días anteriores | Si un Operador corrige un lote de una fecha anterior, el cambio queda propuesto y el lote pasa a "pendiente de aprobación"; los valores no cambian hasta que el Administrador apruebe | Los totales nunca muestran números sin aprobar |
| Lotes cerrados | Se cierran cuando todos los litros tienen destino. Solo el Administrador los edita, con motivo obligatorio y auditado | Pedido de la Fase 2 |
| Alerta de litros | `LECHE_UMBRAL_LITROS_DIARIOS` en `.env`. La alerta de hoy aparece recién cuando están cargados los dos ordeñes; la de ayer, siempre | Evita una falsa alarma a la mañana, antes del ordeñe de la tarde |
| Sin conexión | Si no hay señal al guardar, el lote queda en el teléfono y se envía solo al volver la señal. Cada lote lleva un id generado en el teléfono, así un reintento no duplica | El dueño confirmó que la señal falla en el campo. Requiere tener la app abierta y la sesión iniciada; la app instalable que abre sin señal queda para más adelante |
