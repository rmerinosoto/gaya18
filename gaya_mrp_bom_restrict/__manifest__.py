# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    "name": "Gaya - Restringir lectura de Lista de Materiales (BOM)",
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Solo usuarios con permiso de Manufactura pueden ver/abrir las "
               "listas de materiales (mrp.bom). El acceso de Contabilidad, "
               "Ventas, Compras o Inventario ya NO permite leer una BOM.",
    "author": "ANFEPI: Rodrigo Merino",
    "website": "https://gayamexico.com",
    "license": "LGPL-3",
    "depends": ["mrp", "mrp_account", "sale_mrp", "purchase_mrp"],
    "data": ["security/restrict_bom_access.xml"],
    "installable": True,
    "application": False,
}
