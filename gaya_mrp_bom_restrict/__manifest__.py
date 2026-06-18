# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "Gaya - Restringir lectura de Lista de Materiales (BOM)",
    "version": "18.0.2.1.0",
    "category": "Manufacturing",
    "summary": "Solo Manufactura ve los BOM de manufactura (type=normal). El resto "
               "ve el producto y los kits (phantom, para POS/venta), pero no la "
               "receta de manufactura. Via record rule, no por ACL de modelo.",
    "author": "ANFEPI: Rodrigo Merino",
    "website": "https://gayamexico.com",
    "license": "LGPL-3",
    "depends": ["mrp", "mrp_account", "sale_mrp", "purchase_mrp"],
    "data": [
        "security/ir.model.access.csv",
        "security/bom_visibility_rules.xml",
    ],
    "installable": True,
    "application": False,
}
