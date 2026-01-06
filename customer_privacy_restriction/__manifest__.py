{
    "name": "Gaya Special Customer Privacy",
    "summary": "Restringe las ventas y facturas de clientes marcados como especiales a un grupo de usuarios.",
    "version": "18.0.1.0.0",
    "category": "Sales/CRM",
    "author": "ANFEPI - Rodrigo Merino",
    "depends": ["base", "sale_management", "account"],
    "data": [
        "security/special_customer_security.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "license": "LGPL-3",
    "installable": True,
}
