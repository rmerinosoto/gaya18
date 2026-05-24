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
        tracking=True,
        help="Etapa comercial: Prospecto (todavía no compra), Cliente (ya compró), Inactivo (dejó de comprar).",
        # why: sin default. Antes era "prospect" y ensuciaba 12,505 partners
        # no comerciales (proveedores, contactos internos, sucursales).
    )
    x_channel = fields.Selection(
        [
            ("store", "Tienda"),
            ("restaurant", "Restaurante"),
            ("distributor", "Distribuidor"),
        ],
        string="Canal",
        tracking=True,
        help="Tipo de negocio del cliente: Tienda, Restaurante o Distribuidor.",
    )
    x_visit_frequency = fields.Selection(
        [
            ("weekly", "Semanal"),
            ("biweekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Frecuencia de Visita",
        tracking=True,
        help="Cada cuánto debes visitar a este cliente: cada semana, cada dos semanas, o cada mes.",
    )
