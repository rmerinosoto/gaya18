"""Extensión contable de los Ajustes: ventana de búsqueda de facturas."""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sfa_invoice_lookback_days = fields.Integer(
        string="Antigüedad máxima de factura para 'Facturado Pagado' (días)",
        config_parameter="sales_field_sfa.invoice_lookback_days",
        default=90,
        help="El KPI 'Facturado Pagado' descarta facturas emitidas hace más de "
        "estos días: rara vez se pagan dentro del mes consultado, y reconstruir su "
        "fecha de pago es costoso. Subir el valor incluye más facturas, a costa de "
        "rendimiento.",
    )

    # ---- Ciclo de vida automático del estado de cliente ----
    sfa_auto_promote_customer = fields.Boolean(
        string="Promover a 'Cliente' con la primera factura pagada",
        config_parameter="sales_field_sfa.auto_promote_customer",
        default=True,
        help="Un cron diario marca como Cliente a quien tenga al menos una factura "
        "de cliente pagada (y aún no sea cliente).",
    )
    sfa_distinguish_new_customer = fields.Boolean(
        string="Distinguir etapas del cliente (Nuevo/Regular e Inactivo/Perdido)",
        config_parameter="sales_field_sfa.distinguish_new_customer",
        default=False,
        help="Activa la granularidad del ciclo de vida en ambos extremos: al promover, "
        "el cliente queda como 'Cliente Nuevo' (luego se gradúa a regular); y los Inactivos "
        "que llevan mucho sin comprar pasan a 'Perdido'.",
    )
    sfa_new_customer_mode = fields.Selection(
        selection=[("days", "Por tiempo (días)"), ("invoices", "Por nº de facturas pagadas")],
        string="Graduar 'Cliente Nuevo' a regular",
        config_parameter="sales_field_sfa.new_customer_mode",
        default="days",
    )
    sfa_new_customer_days = fields.Integer(
        string="Días como 'Cliente Nuevo'",
        config_parameter="sales_field_sfa.new_customer_days",
        default=90,
        help="Días desde la primera factura pagada antes de pasar a 'Cliente regular'.",
    )
    sfa_new_customer_invoices = fields.Integer(
        string="Facturas pagadas para ser regular",
        config_parameter="sales_field_sfa.new_customer_invoices",
        default=3,
        help="Nº de facturas pagadas a partir del cual deja de ser 'Cliente Nuevo'.",
    )
    sfa_auto_inactivate = fields.Boolean(
        string="Marcar 'Inactivo' por falta de facturas",
        config_parameter="sales_field_sfa.auto_inactivate",
        default=False,
        help="Un cron diario marca Inactivo a los clientes sin facturas en los últimos N meses.",
    )
    sfa_inactive_months = fields.Integer(
        string="Meses sin facturas para 'Inactivo'",
        config_parameter="sales_field_sfa.inactive_months",
        default=6,
    )
    sfa_lost_months = fields.Integer(
        string="Meses sin facturas para 'Perdido'",
        config_parameter="sales_field_sfa.lost_months",
        default=12,
        help="Un Inactivo que lleva estos meses sin facturas pasa a 'Perdido'. "
        "Solo aplica si la distinción de etapas está activada. Debe ser mayor que "
        "los meses para 'Inactivo'.",
    )
    sfa_at_risk_window_months = fields.Integer(
        string="Antigüedad máxima en 'Clientes en Riesgo' (meses)",
        config_parameter="sales_field_sfa.at_risk_window_months",
        default=24,
        help="Un cliente Inactivo o Perdido cuya última compra sea más antigua que "
        "estos meses deja de aparecer (y de sumar) en el reporte 'Clientes en "
        "Riesgo'. Se mide desde su última compra; el cliente sigue marcado como "
        "Perdido, solo deja de representarse como operación presente. 0 = sin "
        "límite (mostrar siempre).",
    )

    def set_values(self):
        super().set_values()
        # Al guardar Ajustes, re-aplica el ciclo de vida en SEGUNDO PLANO (no bloquea
        # el guardado): dispara el cron para que corra en el siguiente latido (~1 min).
        cron = self.env.ref("sales_field_sfa_account.cron_sfa_status_automation", raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
            _logger.info("sfa lifecycle: cron de estado de cliente disparado tras guardar Ajustes")
