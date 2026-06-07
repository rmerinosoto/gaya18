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
    is_lost = fields.Boolean(
        string="Es Cliente Perdido",
        help="Etapa más profunda que 'Inactivo': cliente sin compras por mucho tiempo. "
        "La automatización lo asigna cuando está activada la distinción de etapas.",
    )


class SalesFieldLostReason(models.Model):
    _name = "sales.field.lost.reason"
    _description = "Motivo de Inactividad/Pérdida (SFA)"
    _order = "sequence, name"

    name = fields.Char(string="Motivo", required=True, translate=True)
    code = fields.Char(string="Código Técnico")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)


class ResPartner(models.Model):
    _inherit = "res.partner"

    sfa_customer_since = fields.Date(
        string="Cliente desde",
        readonly=True,
        help="Fecha de la primera factura pagada del cliente. La asigna la "
        "automatización de estado y sirve para graduar 'Cliente Nuevo' por tiempo.",
    )
    sfa_last_invoice_date = fields.Date(
        string="Última compra",
        readonly=True,
        help="Fecha de la última factura emitida. La actualiza la automatización.",
    )
    sfa_days_since_last_invoice = fields.Integer(
        string="Días sin comprar",
        compute="_compute_sfa_days_since_last_invoice",
        help="Días transcurridos desde la última factura del cliente, a hoy.",
    )
    sfa_inactive_since = fields.Date(
        string="Inactivo desde",
        readonly=True,
        help="Fecha en que la automatización marcó al cliente como Inactivo. Se "
        "limpia si el cliente vuelve a comprar.",
    )
    sfa_inactivity_reason = fields.Many2one(
        "sales.field.lost.reason",
        string="Motivo de inactividad",
        ondelete="restrict",
        tracking=True,
        help="Por qué el cliente está inactivo o perdido. Lo registra Gerencia.",
    )
    sfa_inactivity_note = fields.Text(
        string="Nota de inactividad",
        help="Detalle libre del motivo de inactividad/pérdida.",
    )
    sfa_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda SFA",
        compute="_compute_sfa_currency_id",
    )
    sfa_lost_value = fields.Monetary(
        string="Valor venta perdida (año)",
        currency_field="sfa_currency_id",
        readonly=True,
        help="Facturado en los 12 meses previos a su última compra: la venta anual "
        "que se deja de recibir. La calcula la automatización al marcar Inactivo.",
    )

    @api.depends("sfa_last_invoice_date")
    def _compute_sfa_days_since_last_invoice(self):
        today = fields.Date.context_today(self)
        for p in self:
            p.sfa_days_since_last_invoice = (today - p.sfa_last_invoice_date).days if p.sfa_last_invoice_date else 0

    @api.depends_context("company")
    def _compute_sfa_currency_id(self):
        for p in self:
            p.sfa_currency_id = (p.company_id or self.env.company).currency_id

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
        lost = Status.search([("is_lost", "=", True)], order="sequence", limit=1)
        Move = self.env["account.move"].sudo()
        today = fields.Date.context_today(self)

        distinguish = self._sfa_bool_param("sales_field_sfa.distinguish_new_customer", False)
        mode = self.env["ir.config_parameter"].sudo().get_param("sales_field_sfa.new_customer_mode") or "days"
        new_days = self._sfa_int_param("sales_field_sfa.new_customer_days", 90)
        new_invoices = self._sfa_int_param("sales_field_sfa.new_customer_invoices", 3)
        auto_inactivate = self._sfa_bool_param("sales_field_sfa.auto_inactivate", False)
        inactive_months = self._sfa_int_param("sales_field_sfa.inactive_months", 6)
        lost_months = self._sfa_int_param("sales_field_sfa.lost_months", 12)

        promote_target = new_status if (distinguish and new_status) else regular

        self._sfa_promote_paid_customers(Move, promote_target, today)
        if distinguish and new_status and regular and new_status != regular:
            self._sfa_graduate_new_customers(Move, new_status, regular, mode, new_days, new_invoices, today)
        if auto_inactivate and inactive:
            # 'Perdido' solo se separa si la distinción de etapas está activa.
            lost_target = lost if (distinguish and lost) else None
            self._sfa_inactivate_stale_customers(Move, inactive, inactive_months, lost_target, lost_months, today)

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
                # Reactivación: si venía de Inactivo/Perdido y vuelve a comprar, limpia
                # la marca de inactividad (la razón/nota las gestiona Gerencia).
                "sfa_inactive_since": False,
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
    def _sfa_last_invoice_by_partner(self, Move, partner_ids):
        groups = Move.read_group(
            [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("partner_id", "in", partner_ids)],
            ["partner_id", "invoice_date:max"],
            ["partner_id"],
        )
        return {
            g["partner_id"][0]: fields.Date.to_date(g["invoice_date"])
            for g in groups
            if g.get("partner_id") and g.get("invoice_date")
        }

    @api.model
    def _sfa_write_last_invoice(self, partners, last_by):
        """Actualiza 'última compra' por LOTES (solo donde cambió)."""
        by_date = defaultdict(list)
        for p in partners:
            d = last_by.get(p.id)
            if d and p.sfa_last_invoice_date != d:
                by_date[d].append(p.id)
        for d, pids in by_date.items():
            self.browse(pids).with_context(tracking_disable=True).write({"sfa_last_invoice_date": d})

    @api.model
    def _sfa_lost_value_by_partner(self, Move, partner_ids):
        """Valor de venta perdida = facturado en los 12 meses previos a la última
        compra de cada cliente (ventana propia por cliente). Una sola lectura de
        facturas del conjunto, agregada en Python."""
        moves = Move.search_read(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("partner_id", "in", partner_ids),
                ("invoice_date", "!=", False),
            ],
            ["partner_id", "invoice_date", "amount_total_signed"],
        )
        items = defaultdict(list)
        for m in moves:
            items[m["partner_id"][0]].append((fields.Date.to_date(m["invoice_date"]), m["amount_total_signed"]))
        out = {}
        for pid, rows in items.items():
            last = max(d for d, _ in rows)
            start = last - relativedelta(days=365)
            out[pid] = round(sum(a for d, a in rows if d >= start), 2)
        return out

    @api.model
    def _sfa_inactivate_stale_customers(self, Move, inactive, inactive_months, lost_target, lost_months, today):
        cutoff_inactive = today - relativedelta(months=inactive_months)

        # 1) Clientes activos -> Inactivo por falta de facturas.
        customers = self.search([
            ("sfa_customer_status.is_customer", "=", True),
            ("sfa_excluded", "=", False),
        ])
        if customers:
            last_by = self._sfa_last_invoice_by_partner(Move, customers.ids)
            self._sfa_write_last_invoice(customers, last_by)
            to_inactivate = customers.filtered(
                lambda p: not last_by.get(p.id) or last_by[p.id] < cutoff_inactive
            )
            if to_inactivate:
                # Estado + 'inactivo desde' en un solo write por lote.
                to_inactivate.with_context(tracking_disable=True).write({
                    "sfa_customer_status": inactive.id,
                    "sfa_inactive_since": today,
                })
                # Valor de venta perdida (ventana propia por cliente): se calcula al
                # transicionar y se conserva. Escritura por registro (Monetary no admite
                # write en lote si las monedas difieren entre clientes).
                lost_value = self._sfa_lost_value_by_partner(Move, to_inactivate.ids)
                for p in to_inactivate.with_context(tracking_disable=True):
                    p.sfa_lost_value = lost_value.get(p.id, 0.0)
                _logger.info("sfa lifecycle: %d clientes marcados inactivos", len(to_inactivate))

        # 2) Inactivos -> Perdido (solo si la distinción de etapas está activa).
        if not lost_target:
            return
        cutoff_lost = today - relativedelta(months=lost_months)
        inactives = self.search([
            ("sfa_customer_status", "=", inactive.id),
            ("sfa_excluded", "=", False),
        ])
        if not inactives:
            return
        last_by = self._sfa_last_invoice_by_partner(Move, inactives.ids)
        self._sfa_write_last_invoice(inactives, last_by)
        to_lose = inactives.filtered(
            lambda p: not last_by.get(p.id) or last_by[p.id] < cutoff_lost
        )
        if to_lose:
            to_lose.with_context(tracking_disable=True).write({"sfa_customer_status": lost_target.id})
            _logger.info("sfa lifecycle: %d clientes marcados perdidos", len(to_lose))
