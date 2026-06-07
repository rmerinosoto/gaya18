"""Pre-migración 18.0.2.0.0: renombrar las columnas de res.partner de x_* a sfa_*.

En 18.0.2.0.0 los campos del módulo dejaron el prefijo `x_` (reservado a campos
Studio/manuales) y adoptaron el prefijo de módulo `sfa_`. Renombramos la columna
en disco ANTES de que el ORM cargue los nuevos campos: así Odoo encuentra la
columna ya existente con el nombre nuevo y conserva todos los datos, en lugar de
crear una columna vacía y dejar la vieja huérfana.

Instalación limpia (version vacía): no hay columnas que renombrar, no-op.
"""
import logging

_logger = logging.getLogger(__name__)

# old -> new
RENAMES = {
    "x_customer_status": "sfa_customer_status",
    "x_channel": "sfa_channel",
    "x_visit_frequency": "sfa_visit_frequency",
    "x_sfa_excluded": "sfa_excluded",
    "x_sfa_exclusion_reason": "sfa_exclusion_reason",
}


def _col_exists(cr, table, col):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, col),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        _logger.info("sales_field_sfa 2.0.0 pre: instalación limpia, sin rename")
        return

    for old, new in RENAMES.items():
        if not _col_exists(cr, "res_partner", old):
            _logger.info("sales_field_sfa 2.0.0 pre: columna %s no existe, skip", old)
            continue
        if _col_exists(cr, "res_partner", new):
            # Ya migrada (re-ejecución): no pisar la columna nueva.
            _logger.info("sales_field_sfa 2.0.0 pre: %s ya existe, skip rename", new)
            continue
        cr.execute(f'ALTER TABLE res_partner RENAME COLUMN "{old}" TO "{new}"')
        _logger.info("sales_field_sfa 2.0.0 pre: res_partner.%s -> %s", old, new)
