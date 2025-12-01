# -*- coding: utf-8 -*-
{
    'name': 'Gaya - Fix Global Invoice Access',
    'version': '18.0.1.0.1',
    
    'category': 'Accounting/Localizations',
    'summary': 'Allow invoice users to access Global Invoice wizard without Settings permission',
    'description': """
Fix Global Invoice Access for Invoice Users
============================================

This module adds read access to ir.actions.act_window for users with the 
Invoicing group, allowing them to use the "Create Global Invoice" action 
from POS and Accounting without requiring the Settings permission.

The core issue is that the method l10n_mx_edi_action_create_global_invoice()
returns a dictionary with type 'ir.actions.act_window', and Odoo validates
access to this model which by default requires base.group_system (Settings).

This module adds a minimal read-only access rule for account.group_account_invoice
to resolve the permission error.
    """,
    'author': 'Gaya Vainilla y Especias',
    'depends': [
        'base',
        'account',
        'l10n_mx_edi',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
