"""Objetivos (metas) de facturación por vendedor y mes.

Vive en el módulo puente porque la meta se compara contra el cobro real
(account). Granularidad mensual: el periodo 'año' del dashboard suma las metas
de los 12 meses. La fecha se normaliza al día 1 del mes para tener una clave
estable por (vendedor, mes, compañía).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SalesFieldTarget(models.Model):
    _name = "sales.field.target"
    _description = "Objetivo de Facturación (SFA)"
    _order = "date_month desc, user_id"
    _check_company_auto = True

    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        required=True,
        index=True,
        default=lambda self: self.env.user,
    )
    date_month = fields.Date(
        string="Mes",
        required=True,
        index=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        help="Cualquier día del mes objetivo; se guarda normalizado al día 1.",
    )
    target_amount = fields.Monetary(
        string="Objetivo (cobrado)",
        required=True,
        currency_field="currency_id",
        help="Monto de Facturado Pagado (cobrado) que se espera del vendedor en el mes.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Moneda",
        readonly=True,
    )

    _sql_constraints = [
        (
            "uniq_user_month_company",
            "unique(user_id, date_month, company_id)",
            "Ya existe un objetivo para ese vendedor y mes.",
        ),
    ]

    @api.constrains("target_amount")
    def _check_target_positive(self):
        for rec in self:
            if rec.target_amount < 0:
                raise ValidationError(_("El objetivo no puede ser negativo."))

    @staticmethod
    def _normalize_vals_month(vals):
        if vals.get("date_month"):
            d = fields.Date.to_date(vals["date_month"])
            vals["date_month"] = d.replace(day=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_vals_month(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_vals_month(vals)
        return super().write(vals)

    def name_get(self):
        result = []
        for rec in self:
            label = "%s · %s" % (
                rec.user_id.name or "",
                rec.date_month and rec.date_month.strftime("%Y-%m") or "",
            )
            result.append((rec.id, label))
        return result
