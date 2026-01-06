from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _privacy_group_id(self):
        return "customer_privacy_restriction.group_view_special_customers"

    def _privacy_partner_field(self):
        return "partner_id"

    def _privacy_domain(self):
        partner_field = self._privacy_partner_field()
        return [
            "|",
            (f"{partner_field}.special_privacy_customer", "=", False),
            (partner_field, "=", False),
        ]

    def _apply_privacy_domain(self, domain):
        domain = domain or []
        if self.env.user.has_group(self._privacy_group_id()):
            return domain
        return expression.AND([domain, self._privacy_domain()])

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        domain = self._apply_privacy_domain(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def read_group(
        self,
        domain,
        fields,
        groupby,
        offset=0,
        limit=None,
        orderby=False,
        lazy=True,
    ):
        domain = self._apply_privacy_domain(domain)
        return super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    def check_access_rule(self, operation=None):
        if not self.env.user.has_group(self._privacy_group_id()):
            partner_field = self._privacy_partner_field()
            restricted = self.filtered(
                lambda so: getattr(so, partner_field) and getattr(so, partner_field).special_privacy_customer
            )
            if restricted:
                raise AccessError(_("No tiene permisos para acceder a los documentos de un cliente confidencial."))
        return super().check_access_rule(operation=operation)
