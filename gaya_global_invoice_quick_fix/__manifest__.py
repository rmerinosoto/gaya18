# -*- coding: utf-8 -*-
{
    'name': 'Gaya - Global Invoice Access Quick Fix',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Quick fix for Global Invoice access using sudo()',
    'description': """
Quick Fix for Global Invoice Access
====================================

This is a TEMPORARY quick fix that uses sudo() to bypass the access check.
This allows immediate resolution while the proper ACL-based module is being installed.

For the proper solution, install gaya_l10n_mx_edi_access_fix instead.
    """,
    'author': 'Gaya Vainilla y Especias',
    'depends': [
        'l10n_mx_edi',
        'l10n_mx_edi_pos',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
