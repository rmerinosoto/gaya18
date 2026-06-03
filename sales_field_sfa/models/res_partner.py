from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Los 4 campos pasaron de Selection a Many2one en 18.0.1.0.2 — el admin (gerencia SFA)
    # gestiona los valores desde Seguimiento Comercial → Configuración. La migración
    # 18.0.1.0.2/pre-migrate.py + post-migrate.py preserva los valores existentes.
    x_customer_status = fields.Many2one(
        "sales.field.customer.status",
        string="Estado Cliente",
        tracking=True,
        ondelete="restrict",
        help="Etapa comercial del cliente. Las opciones se gestionan en Seguimiento Comercial → Configuración → Estados de Cliente.",
    )
    x_channel = fields.Many2one(
        "sales.field.channel",
        string="Canal",
        tracking=True,
        ondelete="restrict",
        help="Tipo de negocio del cliente. Las opciones se gestionan en Seguimiento Comercial → Configuración → Canales.",
    )
    x_visit_frequency = fields.Many2one(
        "sales.field.visit.frequency",
        string="Frecuencia de Visita",
        tracking=True,
        ondelete="restrict",
        help="Cada cuánto se visita a este cliente. Las opciones se gestionan en Seguimiento Comercial → Configuración → Frecuencias de Visita.",
    )
    # Exclusion del seguimiento comercial: solo Gerencia puede activarlo. El vendedor
    # ni siquiera ve el campo en la vista (groups en partner_views.xml). tracking=True
    # asegura audit completo en chatter (quien, cuando, motivo).
    x_sfa_excluded = fields.Boolean(
        string="Excluido del Seguimiento Comercial",
        tracking=True,
        help="Si está activado, este cliente no aparece en las listas operativas del módulo de Seguimiento Comercial (Mis Clientes, Clientes del Equipo, Sin contacto 30 días) y los vendedores no pueden registrar interacciones. Solo Gerencia puede modificar este campo.",
    )
    x_sfa_exclusion_reason = fields.Many2one(
        "sales.field.exclusion.reason",
        string="Motivo de Exclusión",
        tracking=True,
        ondelete="restrict",
        help="Razón por la que el cliente no requiere seguimiento comercial. Útil para auditoría. Las opciones se gestionan en Seguimiento Comercial → Configuración → Motivos de Exclusión.",
    )
