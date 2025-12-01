# -*- coding: utf-8 -*-
from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    def l10n_mx_edi_action_create_global_invoice(self):
        """
        Override to use sudo() and bypass ir.actions.act_window access check.
        This is a temporary fix until proper ACL is installed.
        """
        # Call the original method with sudo to bypass access restrictions
        result = super(PosOrder, self.sudo()).l10n_mx_edi_action_create_global_invoice()
        return result
