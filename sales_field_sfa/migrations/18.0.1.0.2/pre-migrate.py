"""Pre-migration 18.0.1.0.2: preservar valores varchar de los campos Selection
que pasaran a ser Many2one.

Estrategia: renombramos las columnas varchar a `<campo>_legacy` antes de que
Odoo recree las columnas como integer (M2O). El post-migrate poblara los M2O
desde las columnas legacy y luego las borrara.

Si esta migration NO se ejecuta (instalacion limpia), no hay nada que preservar
y los M2O quedan NULL — comportamiento esperado.
"""
import logging

_logger = logging.getLogger(__name__)

FIELDS_TO_MIGRATE = [
    "x_customer_status",
    "x_channel",
    "x_visit_frequency",
    "x_sfa_exclusion_reason",
]


def migrate(cr, version):
    if not version:
        _logger.info("sales_field_sfa: instalacion limpia, sin migracion previa")
        return

    # Limpiar las options de Selection viejas en ir.model.fields.selection.
    # Sin esto, Odoo intenta borrarlas mas tarde y falla con AttributeError
    # porque el campo ya esta declarado como M2O (ondelete es string, no dict).
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection s
        USING ir_model_fields f
        WHERE s.field_id = f.id
          AND f.model = 'res.partner'
          AND f.name IN %s
        """,
        (tuple(FIELDS_TO_MIGRATE),),
    )
    _logger.info(
        "sales_field_sfa pre-migrate: borradas %d options de Selection viejas",
        cr.rowcount,
    )

    for field in FIELDS_TO_MIGRATE:
        # Verificar si la columna existe como varchar (Selection viejo).
        cr.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'res_partner' AND column_name = %s
            """,
            (field,),
        )
        row = cr.fetchone()
        if not row:
            _logger.info("sales_field_sfa pre-migrate: columna %s no existe, skip", field)
            continue
        data_type = row[0]
        if data_type == "integer":
            _logger.info("sales_field_sfa pre-migrate: %s ya es integer, skip", field)
            continue
        # Es varchar — renombramos a _legacy para que el post-migrate pueda leer
        # y Odoo cree la nueva columna integer (M2O).
        legacy_col = f"{field}_legacy"
        cr.execute(f"ALTER TABLE res_partner DROP COLUMN IF EXISTS {legacy_col}")
        cr.execute(f"ALTER TABLE res_partner RENAME COLUMN {field} TO {legacy_col}")
        _logger.info(
            "sales_field_sfa pre-migrate: res_partner.%s (varchar) renombrada a %s",
            field, legacy_col,
        )
