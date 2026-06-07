"""Post-migración 18.0.2.0.0: dos ajustes tras cargar el esquema/datos nuevos.

1) Marcar is_prospect=True en el estado 'Prospecto'. El catálogo se carga con
   noupdate="1", así que el valor nuevo del campo NO se aplica a la base que ya
   tenía el registro; lo fijamos aquí para que el KPI "Prospectos Contactados"
   (que ahora filtra por la bandera, no por el code) siga funcionando.

2) Desvincular los catálogos que pasaron de `data` a `demo` (canales y motivos
   de exclusión específicos de Gaya). En una base de PRODUCCIÓN (sin demo) esos
   registros ya existen con datos reales (canales asignados a clientes). Si los
   dejáramos referenciados como datos del módulo, el barrido de huérfanos de Odoo
   los borraría al no hallarlos en el manifest `data` → fallaría por
   ondelete=restrict. Soltamos su ir.model.data y sobreviven como datos de usuario.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlids que se movieron de data/catalogs.xml a demo/catalogs_demo.xml.
DEMOTED_XMLIDS = (
    "channel_store",
    "channel_restaurant",
    "channel_distributor",
    "exclusion_reason_mercado_libre",
    "exclusion_reason_empresa_interna",
    "exclusion_reason_auto_atencion",
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) is_prospect en el estado 'prospect'.
    prospect = env.ref("sales_field_sfa.customer_status_prospect", raise_if_not_found=False)
    if prospect and not prospect.is_prospect:
        prospect.is_prospect = True
        _logger.info("sales_field_sfa 2.0.0 post: is_prospect=True en customer_status_prospect")

    # 2) Detach solo si ESTE módulo NO se instaló con demo (en demo los registros
    #    se recargan correctamente desde el archivo demo y no hay que tocarlos).
    cr.execute("SELECT demo FROM ir_module_module WHERE name = 'sales_field_sfa'")
    row = cr.fetchone()
    if row and row[0]:
        _logger.info("sales_field_sfa 2.0.0 post: módulo con demo, no se desvincula nada")
        return

    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'sales_field_sfa' AND name IN %s",
        (DEMOTED_XMLIDS,),
    )
    _logger.info(
        "sales_field_sfa 2.0.0 post: %d catálogos movidos a demo desvinculados (sobreviven como datos de usuario)",
        cr.rowcount,
    )
