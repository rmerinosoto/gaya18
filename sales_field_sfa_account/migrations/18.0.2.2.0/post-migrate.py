"""Inicializa `sfa_at_risk` al introducir la ventana de 'Clientes en Riesgo'.

El reporte ahora filtra por `sfa_at_risk` (booleano que mantiene el cron). Sin este
backfill, el reporte quedaría vacío hasta la primera corrida del cron tras el deploy.
Aquí lo poblamos de una vez con la ventana configurada (default 24 meses)."""
import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"]
    today = fields.Date.context_today(Partner)
    Partner._sfa_refresh_at_risk(today)
    _logger.info("sfa: sfa_at_risk inicializado tras instalar la ventana de 'Clientes en Riesgo'")
