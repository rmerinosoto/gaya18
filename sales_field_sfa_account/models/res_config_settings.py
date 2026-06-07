"""Ajuste contable del Seguimiento Comercial (ventana de búsqueda de facturas)."""
from odoo import fields, models


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
