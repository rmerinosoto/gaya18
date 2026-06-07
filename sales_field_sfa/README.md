# Sales Field SFA (Odoo 18 Community)

Addon de **seguimiento comercial de campo** con panel OWL. Funciona sobre Odoo 18
**Community** (no requiere Enterprise).

- Modelo `sales.interaction` con chatter y actividades.
- Seguridad por vendedor (cada quien ve solo sus interacciones).
- Menús operativos: interacciones, clientes, cotizaciones.
- Panel OWL con KPIs (mes / año) y listas operativas (hoy / semana / atrasados / sin contacto).
- Catálogos configurables (canal, frecuencia de visita, estado de cliente, motivo de exclusión).
- Flujo de reasignación de clientes con aprobación de Gerencia.
- KPI contable **Facturado Pagado** — opcional, vía módulo puente (ver abajo).

## Arquitectura (desde 18.0.2.0.0)

El producto se reparte en dos módulos para ser reutilizable en cualquier empresa:

| Módulo | Qué aporta | Dependencias |
|--------|------------|--------------|
| **`sales_field_sfa`** (core) | Interacciones, dashboard, catálogos, seguridad, ajustes. | `sale_management`, `mail`, `contacts` |
| **`sales_field_sfa_account`** (puente) | KPI "Facturado Pagado" reconstruyendo la fecha real de pago por conciliación. | `sales_field_sfa`, `account` |

El puente es `auto_install`: se instala solo cuando la base ya tiene `account`.
Si una empresa no usa contabilidad de Odoo, instala solo el core y el dashboard
funciona igual (sin las tarjetas de facturación).

## Reutilización en otras empresas

- **Idiomas:** strings traducibles (Python, vistas, OWL y JS). Ver `i18n/`.
- **Catálogos:** una instalación nueva arranca con catálogos neutros. Los valores
  de ejemplo (Tienda/Restaurante/Distribuidor, Mercado Libre, etc.) son **datos de
  demo** (`demo/catalogs_demo.xml`), no se imponen en producción.
- **Sin `code` hardcodeado:** el dashboard clasifica prospectos/clientes por las
  banderas `is_prospect` / `is_customer` del catálogo, no por un `code` literal.
- **Parámetros configurables** (Seguimiento Comercial → Configuración → Ajustes):
  - Días para "cliente sin contacto" (default 30).
  - Horizonte de "pendientes esta semana" (default 7).
  - Ventana de "interacciones recientes" (default 90).
  - Ocultar el menú CRM a los vendedores (default sí).
  - Antigüedad máxima de factura para el KPI Facturado Pagado (default 90, puente).

## Instalación

1. Copiar `sales_field_sfa` (y opcionalmente `sales_field_sfa_account`) a tu ruta de addons.
2. Actualizar lista de apps.
3. Instalar **Sales Field SFA**. Si tienes Contabilidad, el puente se instala solo.
4. Asignar grupos: `Usuario Seguimiento Comercial` / `Gerente Seguimiento Comercial`.

## Notas funcionales

- Las interacciones se miden por `interaction_datetime`.
- La fecha pagada de factura se calcula con la fecha del asiento de contraparte de
  conciliación (`account.partial.reconcile`), tomando la máxima por factura.
- El panel muestra solo datos del usuario logueado, respetando las reglas de acceso.

## Migración de campos (18.0.2.0.0)

Los campos en `res.partner` pasaron de prefijo `x_` a `sfa_`
(`sfa_customer_status`, `sfa_channel`, `sfa_visit_frequency`, `sfa_excluded`,
`sfa_exclusion_reason`). La migración `migrations/18.0.2.0.0` renombra las columnas
preservando los datos. No requiere intervención manual.
