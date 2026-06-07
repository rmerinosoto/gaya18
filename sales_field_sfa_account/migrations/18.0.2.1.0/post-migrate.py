"""Fija la bandera is_inactive=True en el estado 'Inactivo' del catálogo.

No se puede hacer por data XML: el registro customer_status_inactive lo creó el
core con noupdate=1, así que un -u no lo re-escribe. Aquí lo fijamos por código
(install y upgrade). Idempotente.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    inactive = env.ref("sales_field_sfa.customer_status_inactive", raise_if_not_found=False)
    if inactive and not inactive.is_inactive:
        inactive.is_inactive = True
        _logger.info("sales_field_sfa_account 2.1.0: is_inactive=True en customer_status_inactive")
