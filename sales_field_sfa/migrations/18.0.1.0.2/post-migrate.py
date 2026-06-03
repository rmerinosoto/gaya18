"""Post-migration 18.0.1.0.2: poblar los nuevos M2O desde las columnas
`<campo>_legacy` que el pre-migrate dejo con los valores varchar viejos.

Mapeo varchar→catalogo se hace via xml_id estable definido en data/catalogs.xml.
Si alguna key del legacy no tiene catalogo correspondiente, queda NULL y se
loguea WARNING — el admin puede decidir que hacer despues.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


CATALOG_MAPPING = {
    "x_customer_status": {
        "model": "sales.field.customer.status",
        "xml_id_prefix": "sales_field_sfa.customer_status_",
    },
    "x_channel": {
        "model": "sales.field.channel",
        "xml_id_prefix": "sales_field_sfa.channel_",
    },
    "x_visit_frequency": {
        "model": "sales.field.visit.frequency",
        "xml_id_prefix": "sales_field_sfa.visit_frequency_",
    },
    "x_sfa_exclusion_reason": {
        "model": "sales.field.exclusion.reason",
        "xml_id_prefix": "sales_field_sfa.exclusion_reason_",
    },
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for field, conf in CATALOG_MAPPING.items():
        legacy_col = f"{field}_legacy"
        # Verificar que la columna legacy existe (la dejo el pre-migrate).
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'res_partner' AND column_name = %s
            """,
            (legacy_col,),
        )
        if not cr.fetchone():
            _logger.info("sales_field_sfa post-migrate: %s no existe, skip", legacy_col)
            continue

        # Construir mapeo code → id desde xml_id.
        cr.execute(
            f"SELECT DISTINCT {legacy_col} FROM res_partner WHERE {legacy_col} IS NOT NULL"
        )
        codes = [row[0] for row in cr.fetchall()]
        if not codes:
            _logger.info("sales_field_sfa post-migrate: %s sin datos, skip", legacy_col)
            cr.execute(f"ALTER TABLE res_partner DROP COLUMN {legacy_col}")
            continue

        code_to_id = {}
        for code in codes:
            xml_id = f"{conf['xml_id_prefix']}{code}"
            record = env.ref(xml_id, raise_if_not_found=False)
            if record:
                code_to_id[code] = record.id
            else:
                _logger.warning(
                    "sales_field_sfa post-migrate: no se encontro xml_id %s para code=%r en campo %s — "
                    "los partners con ese valor quedaran NULL",
                    xml_id, code, field,
                )

        # Update masivo: un UPDATE por cada code mapeado.
        total = 0
        for code, target_id in code_to_id.items():
            cr.execute(
                f"UPDATE res_partner SET {field} = %s WHERE {legacy_col} = %s",
                (target_id, code),
            )
            count = cr.rowcount
            total += count
            _logger.info(
                "sales_field_sfa post-migrate: %s='%s' -> id=%d (%d partners)",
                field, code, target_id, count,
            )

        # Una vez migrado, borrar la columna legacy.
        cr.execute(f"ALTER TABLE res_partner DROP COLUMN {legacy_col}")
        _logger.info("sales_field_sfa post-migrate: %s completado, %d partners migrados, legacy borrada", field, total)
