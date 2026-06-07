"""Ciclo de vida del estado de cliente (automatización vía facturas).

Vive en el puente porque todos los disparadores dependen de account:
- Promoción a Cliente con la primera factura pagada.
- Graduación 'Cliente Nuevo' -> 'Cliente regular' por tiempo o por nº de facturas.
- Inactivación por falta de facturas en N meses.

Banderas semánticas en el catálogo (is_customer / is_new_customer / is_inactive)
identifican cada estado sin depender del `code`. Un cron diario aplica las reglas.
"""
import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SalesFieldCustomerStatus(models.Model):
    _inherit = "sales.field.customer.status"

    is_inactive = fields.Boolean(
        string="Es Inactivo",
        help="Estado que la automatización asigna a clientes sin facturas recientes.",
    )
    is_new_customer = fields.Boolean(
        string="Es Cliente Nuevo",
        help="Cliente recién convertido. Cuenta como cliente en los KPIs, pero se "
        "distingue del regular. La automatización lo gradúa a 'Cliente regular'.",
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    sfa_customer_since = fields.Date(
        string="Cliente desde",
        readonly=True,
        help="Fecha de la primera factura pagada del cliente. La asigna la "
        "automatización de estado y sirve para graduar 'Cliente Nuevo' por tiempo.",
    )

    # ---- helpers de parámetros ----
    @api.model
    def _sfa_bool_param(self, key, default):
        # OJO: get_param(key) sin default devuelve False (bool) si la clave no existe,
        # lo que se confundiría con "está en False". Pasamos el default para distinguir
        # "no configurado" (usa default) de "configurado en False".
        raw = self.env["ir.config_parameter"].sudo().get_param(key, default)
        return str(raw).lower() not in ("false", "0", "")

    @api.model
    def _sfa_int_param(self, key, default):
        raw = self.env["ir.config_parameter"].sudo().get_param(key)
        try:
            v = int(raw)
            return v if v > 0 else default
        except (TypeError, ValueError):
            return default

    @api.model
    def _sfa_run_status_automation(self):
        """Punto de entrada del cron. Aplica promoción, graduación e inactivación
        según los ajustes. Idempotente: solo cambia lo que corresponde."""
        Status = self.env["sales.field.customer.status"].sudo()
        regular = Status.search([("is_customer", "=", True), ("is_new_customer", "=", False)], order="sequence", limit=1)
        new_status = Status.search([("is_new_customer", "=", True)], order="sequence", limit=1)
        inactive = Status.search([("is_inactive", "=", True)], order="sequence", limit=1)
        Move = self.env["account.move"].sudo()
        today = fields.Date.context_today(self)

        auto_promote = self._sfa_bool_param("sales_field_sfa.auto_promote_customer", True)
        distinguish = self._sfa_bool_param("sales_field_sfa.distinguish_new_customer", False)
        mode = self.env["ir.config_parameter"].sudo().get_param("sales_field_sfa.new_customer_mode") or "days"
        new_days = self._sfa_int_param("sales_field_sfa.new_customer_days", 90)
        new_invoices = self._sfa_int_param("sales_field_sfa.new_customer_invoices", 3)
        auto_inactivate = self._sfa_bool_param("sales_field_sfa.auto_inactivate", False)
        inactive_months = self._sfa_int_param("sales_field_sfa.inactive_months", 6)

        promote_target = new_status if (distinguish and new_status) else regular

        self._sfa_promote_paid_customers(Move, promote_target, today)
        if distinguish and new_status and regular and new_status != regular:
            self._sfa_graduate_new_customers(Move, new_status, regular, mode, new_days, new_invoices, today)
        if auto_inactivate and inactive:
            self._sfa_inactivate_stale_customers(Move, inactive, inactive_months, today)

    @api.model
    def _sfa_promote_paid_customers(self, Move, promote_target, today):
        if not promote_target:
            return
        if not self._sfa_bool_param("sales_field_sfa.auto_promote_customer", True):
            return
        # Eficiencia: solo CANDIDATOS (aún no clientes, no excluidos). Tras la primera
        # corrida esto es un puñado, así el read_group de facturas se acota a ellos.
        candidates = self.search([
            ("sfa_excluded", "=", False),
            "|",
            ("sfa_customer_status", "=", False),
            ("sfa_customer_status.is_customer", "=", False),
        ])
        if not candidates:
            return
        groups = Move.read_group(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("paid", "in_payment")),
                ("partner_id", "in", candidates.ids),
            ],
            ["partner_id", "invoice_date:min"],
            ["partner_id"],
        )
        # En Odoo 18 read_group devuelve el agregado bajo la clave del campo ('invoice_date').
        first_paid = {
            g["partner_id"][0]: fields.Date.to_date(g["invoice_date"])
            for g in groups
            if g.get("partner_id") and g.get("invoice_date")
        }
        if not first_paid:
            return
        # Escritura por LOTES agrupada por fecha (status + 'cliente desde' juntos) y sin
        # tracking/chatter: cero mail.message, mínimas UPDATE. El audit queda en
        # 'cliente desde' y en el propio estado.
        by_date = defaultdict(list)
        for pid, d in first_paid.items():
            by_date[d].append(pid)
        for d, pids in by_date.items():
            self.browse(pids).with_context(tracking_disable=True).write({
                "sfa_customer_status": promote_target.id,
                "sfa_customer_since": d,
            })
        _logger.info("sfa lifecycle: %d clientes promovidos a '%s'", len(first_paid), promote_target.name)

    @api.model
    def _sfa_graduate_new_customers(self, Move, new_status, regular, mode, new_days, new_invoices, today):
        new_partners = self.search([
            ("sfa_customer_status", "=", new_status.id),
            ("sfa_excluded", "=", False),
        ])
        if not new_partners:
            return
        if mode == "invoices":
            groups = Move.read_group(
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "in", ("paid", "in_payment")),
                    ("partner_id", "in", new_partners.ids),
                ],
                ["partner_id"],
                ["partner_id"],
            )
            count_by = {g["partner_id"][0]: g["partner_id_count"] for g in groups if g.get("partner_id")}
            to_graduate = new_partners.filtered(lambda p: count_by.get(p.id, 0) >= new_invoices)
        else:  # days
            threshold = today - relativedelta(days=new_days)
            to_graduate = new_partners.filtered(lambda p: p.sfa_customer_since and p.sfa_customer_since <= threshold)
        if to_graduate:
            to_graduate.with_context(tracking_disable=True).write({"sfa_customer_status": regular.id})
            _logger.info("sfa lifecycle: %d clientes nuevos graduados a regular", len(to_graduate))

    @api.model
    def _sfa_inactivate_stale_customers(self, Move, inactive, inactive_months, today):
        cutoff = today - relativedelta(months=inactive_months)
        customers = self.search([
            ("sfa_customer_status.is_customer", "=", True),
            ("sfa_excluded", "=", False),
        ])
        if not customers:
            return
        groups = Move.read_group(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("partner_id", "in", customers.ids),
            ],
            ["partner_id", "invoice_date:max"],
            ["partner_id"],
        )
        last_invoice = {
            g["partner_id"][0]: fields.Date.to_date(g["invoice_date"])
            for g in groups
            if g.get("partner_id") and g.get("invoice_date")
        }
        to_inactivate = customers.filtered(
            lambda p: not last_invoice.get(p.id) or last_invoice[p.id] < cutoff
        )
        if to_inactivate:
            to_inactivate.with_context(tracking_disable=True).write({"sfa_customer_status": inactive.id})
            _logger.info("sfa lifecycle: %d clientes marcados inactivos", len(to_inactivate))
