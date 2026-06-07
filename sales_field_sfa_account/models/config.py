"""Extensión contable del asistente de Ajustes: ventana de búsqueda de facturas."""
from odoo import api, fields, models


class SalesFieldConfig(models.TransientModel):
    _inherit = "sales.field.config"

    sfa_invoice_lookback_days = fields.Integer(
        string="Antigüedad máxima de factura para 'Facturado Pagado' (días)",
        default=90,
        help="El KPI 'Facturado Pagado' descarta facturas emitidas hace más de "
        "estos días: rara vez se pagan dentro del mes consultado, y reconstruir su "
        "fecha de pago es costoso. Subir el valor incluye más facturas, a costa de "
        "rendimiento.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        raw = self.env["ir.config_parameter"].sudo().get_param("sales_field_sfa.invoice_lookback_days")
        try:
            res["sfa_invoice_lookback_days"] = int(raw) if int(raw) > 0 else 90
        except (TypeError, ValueError):
            res["sfa_invoice_lookback_days"] = 90
        return res

    def _sfa_save_extra(self):
        super()._sfa_save_extra()
        self.env["ir.config_parameter"].sudo().set_param(
            "sales_field_sfa.invoice_lookback_days", self.sfa_invoice_lookback_days or 90
        )
