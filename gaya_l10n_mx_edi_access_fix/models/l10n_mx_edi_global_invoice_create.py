# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class L10nMxEdiGlobalInvoiceCreate(models.Model):
    _inherit = 'l10n_mx_edi.global_invoice.create'

    def action_create_global_invoice(self):
        """Override to execute with sudo() privileges.
        
        This allows users with the Invoicing group to create global invoices
        without requiring Settings permission.
        """
        _logger.info(
            "Creating global invoice with sudo() for user %s (%s)",
            self.env.user.id,
            self.env.user.name
        )
        return super(L10nMxEdiGlobalInvoiceCreate, self.sudo()).action_create_global_invoice()
