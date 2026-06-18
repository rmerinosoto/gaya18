# -*- coding: utf-8 -*-
{
    'name': 'Gaya - Track Internal Reference Changes',
    'version': '18.0.1.0.0',
    'author': 'ANFEPI: Rodrigo Merino Soto',
    'category': 'Inventory/Inventory',
    'summary': 'Log changes to the product Internal Reference (default_code) in the chatter',
    'description': """
Track Internal Reference (default_code) in the chatter
======================================================

Marks ``default_code`` as a tracked field on both ``product.template`` and
``product.product`` so any change (set, edit or clear) is recorded in the
product chatter with old -> new value and the responsible user.

Why both models:
- Editing the reference on the product *template* form writes to
  ``product.template`` (computed/stored + inverse).
- Editing it on a *variant* form writes to ``product.product`` (the real
  stored field).
Tracking on a single model would miss one of the two edit paths.

Note: tracking only records changes from installation onward; it cannot
recover past deletions.
    """,
    'depends': [
        'product',
        'mail',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
