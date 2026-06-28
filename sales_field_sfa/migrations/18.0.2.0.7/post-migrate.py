"""Post-migración 18.0.2.0.7: refresca traducciones es_MX stale tras el rename
'Canal' → 'Tipo de Negocio' (v18.0.2.0.6).

El rename cambió el source (en_US) de varios términos user-facing, pero Odoo
PRESERVA las traducciones es_MX existentes en un `-u` (no las pisa, para no
clobberar traducciones de usuario). Como este módulo se redacta en español
(el source ES el texto final) y la DB de Gaya corre en es_MX, eso dejó valores
viejos ("Canales", "Canal comercial…") visibles para el usuario aunque el código
ya diga "Tipo de Negocio".

Las etiquetas de los campos (field_description) sí se refrescaron solas; lo que
quedó stale: el nombre de la acción y del menú de configuración, y el help de los
campos sfa_channel / partner_channel. Forzamos es_MX = en_US (el source nuevo)
para esos términos. Idempotente: re-ejecutar solo vuelve a copiar el source.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # name (jsonb) de la acción y el menú de "Tipos de Negocio".
    cr.execute(
        """
        UPDATE ir_act_window a
           SET name = jsonb_set(a.name, '{es_MX}', a.name->'en_US')
          FROM ir_model_data d
         WHERE d.res_id = a.id AND d.model = 'ir.actions.act_window'
           AND d.module = 'sales_field_sfa' AND d.name = 'action_sales_field_channel'
           AND a.name ? 'en_US'
        """
    )
    cr.execute(
        """
        UPDATE ir_ui_menu m
           SET name = jsonb_set(m.name, '{es_MX}', m.name->'en_US')
          FROM ir_model_data d
         WHERE d.res_id = m.id AND d.model = 'ir.ui.menu'
           AND d.module = 'sales_field_sfa' AND d.name = 'menu_sales_field_config_channel'
           AND m.name ? 'en_US'
        """
    )

    # help (jsonb) de los campos renombrados.
    cr.execute(
        """
        UPDATE ir_model_fields
           SET help = jsonb_set(help, '{es_MX}', help->'en_US')
         WHERE help ? 'en_US'
           AND ( (model = 'res.partner'      AND name = 'sfa_channel')
              OR (model = 'sales.interaction' AND name = 'partner_channel') )
        """
    )
    _logger.info(
        "sales_field_sfa 2.0.7 post: traducciones es_MX refrescadas (acción/menú/help) tras rename a 'Tipo de Negocio'"
    )
