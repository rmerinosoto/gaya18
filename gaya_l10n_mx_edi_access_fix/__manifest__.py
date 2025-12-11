# -*- coding: utf-8 -*-
{
    'name': 'Gaya - Fix Global Invoice Access',
    'version': '18.0.1.0.15',
    'author':'ANFEPI: Rodrigo Merino Soto',
    'category': 'Accounting/Localizations',
    'summary': 'Allow invoice users to create Global Invoices from POS without Settings permission',
    'description': """
Fix Global Invoice Access for Invoice Users
============================================

This module allows users with the Invoicing group (account.group_account_invoice)
to create Global Invoices from POS without requiring Settings permission
(base.group_system).

The solution overrides the action_create_global_invoice() method in the
l10n_mx_edi.global_invoice.create wizard to execute with sudo() privileges,
bypassing permission checks that would otherwise block non-admin users.

Key features:
- Overrides l10n_mx_edi.global_invoice.create wizard
- Uses sudo() to bypass permission restrictions
- Includes detailed logging for troubleshooting
- Must load after l10n_mx_edi_pos to ensure proper method resolution order
    """,
    'depends': [
        'l10n_mx_edi',
        'l10n_mx_edi_pos',
    ],
    'data': [],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
