from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    special_privacy_customer = fields.Boolean(
        string="Cliente confidencial",
        help=(
            "Si se activa, solo los usuarios del grupo \"Ver clientes "
            "confidenciales\" podrán acceder a sus ventas y facturas."
        ),
    )
