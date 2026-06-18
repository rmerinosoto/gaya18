# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "Gaya - Restringir lectura de Lista de Materiales (BOM)",
    "version": "18.0.2.0.0",
    "category": "Manufacturing",
    "summary": "Solo usuarios con permiso de Manufactura ven las listas de "
               "materiales (mrp.bom). El resto SI ve el producto, pero ninguna "
               "lista de materiales (via record rule, no por ACL de modelo).",
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
