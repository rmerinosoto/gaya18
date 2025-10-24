# -*- coding: utf-8 -*-
{
    'name': 'Example Module',
    'version': '18.0.1.0.0',
    'category': 'Custom',
    'summary': 'Template module for Gaya18 custom addons',
    'description': """
        Example Module for Gaya18
        ==========================
        
        This is a template module that demonstrates the basic structure
        of an Odoo 18 custom addon.
        
        Features:
        ---------
        * Example model with basic fields
        * Tree and form views
        * Menu items
        * Access rights configuration
        
        How to use:
        -----------
        1. Copy this module as a template
        2. Rename all files and references
        3. Customize according to your needs
        4. Install from Apps menu
    """,
    'author': 'Gaya18 Team',
    'website': 'https://github.com/rmerinosoto/gaya18',
    'license': 'LGPL-3',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/example_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
