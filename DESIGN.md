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
- **Ventas:** cada cliente tiene su condición (contado o crédito a 7, 15 o 30 días); define el vencimiento de su cuenta por cobrar.

## Plan de fases

1. Setup, base de datos, autenticación, usuarios, roles, permisos y auditoría base. ← **hecho**
2. Producción de leche: lotes por sesión de ordeñe, destinos con saldo, correcciones con aprobación,
   panel con alertas y carga sin conexión. ← **hecho**
3. Rodeo y ordeñe por vaca; inventario e insumos; lotes de queso con aprobación y trazabilidad. ← **hecho**
   (Las compras formales pasan a la Fase 5.)
4. Clientes, ventas, entregas, cuentas por cobrar y cobros; pantalla de usuarios y roles. ← **hecho**
5. Gastos, bandeja de aprobaciones, cierre de mes. ← **hecho**
6. Reportes, tablero del dueño, bandeja de control, alertas y pantalla de auditoría. ← **hecho**
   (La importación de planillas no entró en el pedido de la Fase 6: queda para cuando el dueño la pida.)
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

## Decisiones de la Fase 3 (queso, inventario y ordeñe por vaca)

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Ordeñe por vaca | Planilla por sesión (fecha + mañana/tarde) que se guarda completa. La suma de las vacas es el total del lote de leche de esa sesión; si el lote ya existía cargado como total, pasa a ser la suma | Una sola cifra para la sesión: el panel de leche y el rodeo nunca muestran números distintos. Reenviar la planilla no duplica, así funciona sin señal |
| Correcciones por vaca | El operador corrige la planilla del día; los días anteriores y los lotes cerrados solo el Administrador (con motivo en los cerrados) | Mismo criterio que la Fase 2 |
| Tendencia | Promedio diario de los últimos 7 días contra los 7 anteriores; ±5 % marca suba o baja | Simple de leer en el campo; el umbral es fácil de ajustar después |
| Stock | Nunca se guarda: se calcula sumando movimientos. Los movimientos son de solo inserción (trigger de PostgreSQL) y un error se corrige con un movimiento contrario | Consistente y auditable: cada número tiene su rastro |
| Lote de origen | La base exige que todo movimiento de leche tenga su lote de leche, todo movimiento de queso su lote de queso y toda reserva o consumo para elaborar su lote de queso | Pedido de la Fase 3, garantizado por la base y no solo por el código |
| Leche para queso | Un lote de queso usa primero los litros ya destinados a "queso" y después el saldo sin destino. Si usa una parte, el destino se parte en dos | Así encaja con los destinos de la Fase 2 sin tocar los totales de leche |
| Insumos | Al iniciar se reservan (no salen del stock pero no están disponibles para otro lote). Al cerrar se libera la reserva y se descuenta lo usado de verdad, que puede ser distinto | Lo que se declara al empezar rara vez coincide exacto con lo que se usa |
| Queso al inventario | Entra al cerrar el lote (kg obtenidos menos merma), pero solo está disponible para vender cuando el Administrador aprueba | Pedido: "al finalizar se genera inventario"; la aprobación decide si se puede vender |
| Rendimiento | Litros de leche ÷ kg obtenidos. Rango esperado en `.env` (`QUESO_RENDIMIENTO_MIN_L_KG` = 7, `MAX` = 11); fuera del rango, el lote queda marcado y se ve en rojo | Valores iniciales razonables para queso Paraguay; conviene ajustarlos con los datos reales del tambo |
| Aprobación | Solo quien tiene el permiso de aprobar (el Administrador). Además, nadie que no sea el dueño puede aprobar un lote que inició o cerró, aunque se le dé ese permiso en el futuro | Cumple "un Operador no puede aprobar su propio lote" aunque se creen roles nuevos |
| Rechazo | Exige comentario. El lote se corrige (kg, merma, consumos) y se vuelve a enviar; solo se mueven las diferencias | El historial muestra cada vuelta |
| Cancelar | Un lote en elaboración se cancela con motivo: se liberan las reservas y la leche queda otra vez destinada a queso | Errores o tandas perdidas no deben trabar el stock |
| Trazabilidad | Vacas → lote de leche → lote de queso → insumos (con lote del proveedor de las últimas compras) → clientes. También al revés, desde el lote de leche | Pedido de la Fase 3 |

## Decisiones de la Fase 4 (ventas)

| Tema | Decisión | Por qué |
| ---- | -------- | ------- |
| Confirmar la venta | Registrar una venta ya la confirma: en la misma transacción se valida el stock, se descuenta lote por lote y nace la cuenta por cobrar. Si algo falla, no queda nada | El pedido: "al confirmar se descuenta el inventario" sin pasos intermedios que se olviden |
| Qué se puede vender | Queso: solo de lotes aprobados, del más viejo al más nuevo, y nunca de un lote elaborado después de la fecha de la venta. Leche: de cualquier lote con litros sin usar, del más viejo al más nuevo (primero lo ya destinado a venta, después el saldo sin destino) | Primero sale lo más viejo. El dueño pidió no limitar la antigüedad de la leche |
| Precios | Tabla con precio base, por tipo de cliente y por volumen (cantidad mínima). Se aplica el más bajo que corresponda. Solo el Administrador cambia la tabla o vende fuera de lista; queda registrado el precio de lista de cada venta | Pedido de la Fase 4; el precio de lista guardado permite ver descuentos después |
| Estados | Pendiente de entrega → Entregada → Cobrada (cuando el saldo llega a cero). La cuenta: pendiente, cobrada en parte, cobrada | Lo que pidió el diseño, con cobros parciales |
| Anular | Solo el Administrador, con motivo y sin cobros vigentes (primero se anulan los cobros). El stock vuelve a su lote con un movimiento de devolución; nada se borra | Los movimientos de inventario no se editan ni borran |
| Lotes vendidos | Un lote de leche con ventas no se puede anular ni quitarle el destino usado | No romper la trazabilidad |
| Información financiera | La vista global de cuentas por cobrar y el resumen (vendido, cobrado, vencido) requieren `reportes.financieros`, que solo tiene el Administrador. Ventas ve el saldo de cada cliente y de cada venta para poder cobrar | "Ventas no accede a reportes financieros globales" |
| Operador | Ve ventas, clientes y precios; no registra ni edita | Pedido de la Fase 4 |

## Decisiones de la Fase 5 (proveedores, gastos y compras)

| Tema | Decisión | Por qué |
| ---- | -------- | ------- |
| Aprobación de gastos | Un gasto de hasta `GASTO_MONTO_APROBACION` (Gs. 500.000 por defecto, en el `.env`) se aprueba solo al guardarlo. Uno mayor queda *Pendiente* hasta que el Administrador lo apruebe o rechace. Lo que carga el propio Administrador queda aprobado | Pedido de la Fase 5. El Administrador no necesita aprobarse a sí mismo |
| Rechazo | Rechazar exige un comentario. Quien lo cargó lo ve y puede corregir el gasto y volver a enviarlo; la corrección vuelve a pasar por la regla del monto | Que el rechazo diga qué arreglar |
| Quién ve qué | Operador y Ventas ven solo los gastos que cargaron (`gastos.ver`); el Administrador ve todos (`gastos.ver_todos`) | Criterio de aceptación de la Fase 5 |
| Auditoría | Cada gasto y compra guarda quién lo cargó, quién lo aprobó y cuándo. La aprobación automática queda marcada como tal | "Quién aprobó y cuándo" |
| Comprobantes | Foto (JPEG, PNG, WebP, HEIC) o PDF de hasta `COMPROBANTE_MAX_MB` (8 MB). El celular achica la foto a 1600 px antes de subirla. Se revisa el tipo real del archivo, no solo la extensión. Se guarda fuera del sitio público y solo se baja con sesión iniciada | Fotos de celular pesadas y señal débil en el campo; los comprobantes no deben quedar a la vista de cualquiera |
| Compras | Registrar una compra ya la confirma: en la misma transacción entra el stock (con el lote del proveedor, si se indica) y nace la cuenta por pagar con el vencimiento según la condición (contado, 15, 30 o 60 días). Si algo falla, no queda nada | "Al confirmar una compra, entrada automática al inventario y cuenta por pagar" |
| Pagos a proveedores | Solo el Administrador ve las cuentas por pagar y registra pagos (`compras.pago.registrar`). Una compra de contado se puede marcar como ya pagada al cargarla | Información financiera, igual que las cuentas por cobrar |
| Anular compras | Solo el Administrador, con motivo, sin pagos vigentes y solo si el stock que entró sigue disponible. Se descuenta con un movimiento de anulación; nada se borra | Los movimientos de inventario no se editan ni borran |
| Bandeja de aprobación | Muestra los gastos pendientes para decidir ahí mismo, con la foto, y avisa de lotes de queso y correcciones de leche que esperan al Administrador | Un solo lugar para todo lo pendiente |


## Decisiones de la Fase 6 (tablero, reportes y control)

| Tema | Decisión | Por qué |
| ---- | -------- | ------- |
| Estado de resultados | Resultado = ventas no anuladas − gastos **aprobados** − compras de insumos **confirmadas**, todo por fecha dentro del período. Los gastos pendientes se muestran aparte y no restan | Criterio de aceptación: "ventas − gastos del período". El dueño eligió que los insumos cuenten **cuando se compran** (26/11/2026) |
| Costo del litro | Gastos aprobados del centro *Producción de leche* del mes ÷ litros ordeñados del mes | Lo que cuesta producir cada litro, sin inventar prorrateos |
| Costo de un lote de queso | Litros usados × costo del litro + insumos consumidos al precio promedio ponderado de compra (hasta la fecha del lote) + su parte de los gastos del centro *Elaboración de queso* del mes, repartida por litros procesados | Rentabilidad por lote pedida en la Fase 6. Si un insumo nunca se compró, no suma costo y el reporte lo avisa |
| Ingresos de un lote | Cada venta se reparte entre los lotes que salió, en proporción a los kg | Una venta puede salir de varios lotes |
| Margen por producto | Ingresos − costo de lo vendido (no de lo producido). Los gastos de Administración se muestran aparte | Que el margen no castigue el queso que todavía está en stock |
| Flujo de caja | Plata que entra (cobros vigentes) y sale (pagos a proveedores y gastos aprobados) por día o por mes, con acumulado | Las ventas a crédito entran cuando se cobran, no cuando se venden |
| Quién ve qué | El Operador ve producción y alertas operativas. Plata, reportes financieros, bandeja y auditoría son solo del Administrador (403 por API) | Criterio de aceptación de la Fase 6 |
| Registros editados | La bandeja lista ediciones de registros cerrados o aprobados, correcciones aplicadas, reaperturas y anulaciones de cobros, pagos o registros aprobados. "Revisado" se guarda aparte (`revisiones_registro`) porque la auditoría no se modifica | Control del dueño sin tocar la tabla inmutable |
| Alertas | Umbrales en la configuración del establecimiento (no en el `.env`), editables por el Administrador y auditados. Producción baja mira los últimos 7 días (hoy solo cuando ya hay ordeñe cargado) | Que el dueño las ajuste sin tocar el servidor |
| Exportes | PDF (reportlab) y Excel (openpyxl) generados en el servidor con el mismo cálculo que la pantalla. Nombre: `reporte_desde_hasta` | Que el archivo coincida con lo que se ve |
