"""Modelos catalogo del modulo SFA.

Cada modelo reemplaza un Selection hardcodeado en el codigo. El admin (gerencia
SFA) puede agregar, desactivar o renombrar registros desde Seguimiento Comercial
→ Configuracion. El campo `code` es la clave tecnica referenciada desde el
codigo (dashboard, constraints) y NO debe modificarse sin coordinacion.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalesFieldChannel(models.Model):
    _name = "sales.field.channel"
    _description = "Canal Comercial (SFA)"
    _order = "sequence, name"

    name = fields.Char(string="Canal", required=True, translate=True)
    code = fields.Char(
        string="Código Técnico",
        required=True,
        help="Clave técnica referenciada desde código. No modificar sin coordinación con TI.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código técnico debe ser único."),
    ]


class SalesFieldVisitFrequency(models.Model):
    _name = "sales.field.visit.frequency"
    _description = "Frecuencia de Visita (SFA)"
    _order = "sequence, name"

    name = fields.Char(string="Frecuencia", required=True, translate=True)
    code = fields.Char(
        string="Código Técnico",
        required=True,
        help="Clave técnica referenciada desde código. No modificar sin coordinación con TI.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código técnico debe ser único."),
    ]


class SalesFieldCustomerStatus(models.Model):
    _name = "sales.field.customer.status"
    _description = "Estado de Cliente (SFA)"
    _order = "sequence, name"

    name = fields.Char(string="Estado", required=True, translate=True)
    code = fields.Char(
        string="Código Técnico",
        required=True,
        help="Clave técnica referenciada desde código. No modificar sin coordinación con TI.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    # Bandera semantica para el dashboard: KPI "Clientes Contactados" cuenta solo
    # registros con is_customer=True; "Prospectos Contactados" los demas.
    # Sin este flag, agregar un estado nuevo dejaria al dashboard sin saber donde
    # contarlo.
    is_customer = fields.Boolean(
        string="Es Cliente activo",
        help="Marca este estado como 'cliente convertido' (no prospecto ni inactivo). Afecta a qué KPI del dashboard cuenta los partners con este estado.",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código técnico debe ser único."),
    ]


class SalesFieldExclusionReason(models.Model):
    _name = "sales.field.exclusion.reason"
    _description = "Motivo de Exclusión del Seguimiento (SFA)"
    _order = "sequence, name"

    name = fields.Char(string="Motivo", required=True, translate=True)
    code = fields.Char(
        string="Código Técnico",
        required=True,
        help="Clave técnica referenciada desde código. No modificar sin coordinación con TI.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código técnico debe ser único."),
    ]
