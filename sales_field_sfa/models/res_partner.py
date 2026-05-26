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
    # Exclusion del seguimiento comercial: solo Gerencia puede activarlo. El vendedor
    # ni siquiera ve el campo en la vista (groups en partner_views.xml). tracking=True
    # asegura audit completo en chatter (quien, cuando, motivo).
    x_sfa_excluded = fields.Boolean(
        string="Excluido del Seguimiento Comercial",
        tracking=True,
        help="Si está activado, este cliente no aparece en las listas operativas del módulo de Seguimiento Comercial (Mis Clientes, Clientes del Equipo, Sin contacto 30 días) y los vendedores no pueden registrar interacciones. Solo Gerencia puede modificar este campo.",
    )
    x_sfa_exclusion_reason = fields.Selection(
        [
            ("mercado_libre", "Mercado Libre / Marketplace"),
            ("empresa_interna", "Empresa interna o filial"),
            ("auto_atencion", "Cliente con autoservicio (no requiere seguimiento)"),
            ("otro", "Otro motivo"),
        ],
        string="Motivo de Exclusión",
        tracking=True,
        help="Razón por la que el cliente no requiere seguimiento comercial. Útil para auditoría y para entender por qué un cliente quedó fuera del módulo.",
    )
