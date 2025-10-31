# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class Onboarding(models.Model):
    _inherit = 'onboarding.onboarding'

    # Shopify Dashboard Onboarding
    @api.model
    def action_close_panel_woo_commerce_dashboard(self):
        self.action_close_panel('woo_commerce_ept.woo_instances_onboarding_panel_ept')
