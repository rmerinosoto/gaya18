from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_customer_status = fields.Selection(
        [
            ("prospect", "Prospecto"),
            ("customer", "Cliente"),
            ("inactive", "Inactivo"),
        ],
        string="Estado Cliente",
        default="prospect",
        tracking=True,
    )
    x_channel = fields.Selection(
        [
            ("store", "Tienda"),
            ("restaurant", "Restaurante"),
            ("distributor", "Distribuidor"),
        ],
        string="Canal",
        tracking=True,
    )
    x_visit_frequency = fields.Selection(
        [
            ("weekly", "Semanal"),
            ("biweekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Frecuencia de Visita",
        tracking=True,
    )
