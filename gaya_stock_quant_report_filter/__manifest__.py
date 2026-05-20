# -*- coding: utf-8 -*-
{
    'name': 'Gaya - Stock Quant Report Filter',
    'version': '18.0.1.0.2',
    'author': 'ANFEPI: Rodrigo Merino',
    'category': 'Inventory/Inventory',
    'summary': 'Restringe el reporte Inventario/Reportes/Ubicaciones a ubicaciones internas',
    'description': """
Stock Quant Report Filter
=========================

Sobrescribe la acción de servidor `stock.action_view_quants` (menú
Inventario > Reportes > Ubicaciones) para fijar el dominio a quants en
ubicaciones internas (`location.usage = 'internal'`).

Motivo
------
El reporte original incluía quants en ubicaciones virtuales (Proveedor,
Cliente, Inter-company transit) cuyo `company_id` es NULL. Cuando esos
quants referenciaban productos cuyo `product.template.company_id`
pertenecía a otra compañía (Gaya Imports, Gayagua, Beneficio Vainilla
2021), la regla multi-company de `product.template` bloqueaba la lectura
indirecta de `product.product` y disparaba el AccessError:

    "no tiene acceso 'leer' a: Variante del producto (product.product)
     Se accedió implícitamente a través de 'Variante del producto'."

El filtro `usage='internal'` excluye 100% de esos quants (536 en producción
al 2026-05-19) sin tocar el modelo de datos ni ampliar permisos del usuario.
""",
    'depends': ['stock'],
    'data': [
        'data/ir_actions_server.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
