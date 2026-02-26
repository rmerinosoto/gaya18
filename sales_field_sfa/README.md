# Sales Field SFA (Odoo 18 Enterprise)

Addon para seguimiento comercial de campo con:

- Modelo `sales.interaction` con chatter y actividades.
- Seguridad por vendedor (solo sus clientes/interacciones).
- Menús operativos para interacciones, clientes y cotizaciones.
- Panel OWL con KPIs mensuales y listas operativas.
- KPI contable **Facturado Pagado del Mes** usando fecha real de pago por conciliación.

## Dependencias

- `base`
- `mail`
- `contacts`
- `sale_management`
- `account`
- `web`

## Instalación

1. Copiar carpeta `sales_field_sfa` a tu ruta de addons.
2. Actualizar lista de apps.
3. Instalar módulo **Sales Field SFA**.
4. Asignar grupos:
   - `Usuario Seguimiento Comercial`
   - `Gerente Seguimiento Comercial`

## Notas funcionales

- Las interacciones se miden por `interaction_datetime`.
- La fecha pagada de factura se calcula con la fecha del asiento de contraparte de conciliación (`account.partial.reconcile`) y se usa la máxima fecha detectada por factura.
- El panel muestra solo datos del usuario logueado respetando reglas de acceso.
