"""Extensión contable del dashboard de Seguimiento Comercial.

El core (`sales_field_sfa`) no depende de `account` y deja un seam,
`_sfa_extend_dashboard`, que aquí sobreescribimos para inyectar el KPI
"Facturado Pagado" — tanto la tarjeta del vendedor como el desglose por
vendedor del panel gerencial.

La fecha real de pago se reconstruye desde las conciliaciones
(account.partial.reconcile), porque payment_state='paid' no expone la fecha del
pago. Se toma la fecha del asiento de contraparte (la máxima por factura).
"""
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models


class SalesFieldDashboard(models.AbstractModel):
    _inherit = "sales.field.dashboard"

    @api.model
    def _get_paid_date_by_invoice(self, invoices):
        paid_dates = {invoice.id: False for invoice in invoices}
        if not invoices:
            return paid_dates

        line_model = self.env["account.move.line"]
        partial_model = self.env["account.partial.reconcile"]

        receivable_lines = line_model.search(
            [
                ("move_id", "in", invoices.ids),
                ("account_id.account_type", "=", "asset_receivable"),
            ]
        )
        if not receivable_lines:
            return paid_dates

        invoice_by_line = {line.id: line.move_id.id for line in receivable_lines}
        partials = partial_model.search(
            [
                "|",
                ("debit_move_id", "in", receivable_lines.ids),
                ("credit_move_id", "in", receivable_lines.ids),
            ]
        )
        if not partials:
            return paid_dates

        counterpart_line_ids = set()
        for part in partials:
            debit_id = part.debit_move_id.id
            credit_id = part.credit_move_id.id
            if debit_id in invoice_by_line:
                counterpart_line_ids.add(credit_id)
            if credit_id in invoice_by_line:
                counterpart_line_ids.add(debit_id)

        counterpart_lines = line_model.browse(list(counterpart_line_ids)).exists()
        counterpart_move_date = {
            line.id: line.move_id.date for line in counterpart_lines if line.move_id
        }

        dates_by_invoice = defaultdict(list)
        for part in partials:
            debit_id = part.debit_move_id.id
            credit_id = part.credit_move_id.id

            if debit_id in invoice_by_line:
                inv_id = invoice_by_line[debit_id]
                pay_date = counterpart_move_date.get(credit_id)
                if pay_date:
                    dates_by_invoice[inv_id].append(pay_date)

            if credit_id in invoice_by_line:
                inv_id = invoice_by_line[credit_id]
                pay_date = counterpart_move_date.get(debit_id)
                if pay_date:
                    dates_by_invoice[inv_id].append(pay_date)

        for invoice_id, dates in dates_by_invoice.items():
            if dates:
                paid_dates[invoice_id] = max(dates)

        # why: facturas marcadas paid sin reconcile (refund autoaplicado, asiento
        # manual) quedaban en False y desaparecian del KPI. Fallback a la fecha
        # de la propia factura — mejor sub-aproximacion que perder el dato.
        for inv in invoices:
            if not paid_dates.get(inv.id):
                paid_dates[inv.id] = inv.invoice_date or inv.date
        return paid_dates

    @api.model
    def _sfa_invoice_lookback_days(self):
        # Reusa el lector robusto de parametros enteros del core.
        return self._sfa_get_int_param("sales_field_sfa.invoice_lookback_days", 90)

    @api.model
    def _sfa_seller_invoice_domain(self, seller_ids, allowed_company_ids):
        """Domain base de facturas de cliente atribuibles a los vendedores dados
        (por vendedor de la factura, o por vendedor del cliente si la factura no
        lo trae). Excluye clientes marcados sfa_excluded."""
        return [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("company_id", "in", allowed_company_ids),
            ("partner_id.sfa_excluded", "=", False),
            "|",
            ("invoice_user_id", "in", seller_ids),
            "&",
            ("invoice_user_id", "=", False),
            ("partner_id.user_id", "in", seller_ids),
        ]

    @api.model
    def _sfa_compute_billing(self, seller_ids, allowed_company_ids, month_start, month_end, today):
        """Calcula, por vendedor: Facturado del periodo (por invoice_date) y
        Cartera Vencida a hoy (residual abierto con vencimiento pasado).
        Devuelve 4 dicts keyed por seller_id."""
        invoice_model = self.env["account.move"]
        base = self._sfa_seller_invoice_domain(seller_ids, allowed_company_ids)
        seller_set = set(seller_ids)

        def _seller_of(inv):
            s = inv.invoice_user_id or inv.partner_id.user_id
            return s.id if s and s.id in seller_set else None

        invoiced_by, invoiced_ids = defaultdict(float), defaultdict(list)
        for inv in invoice_model.search(base + [
            ("invoice_date", ">=", month_start.isoformat()),
            ("invoice_date", "<=", month_end.isoformat()),
        ]):
            sid = _seller_of(inv)
            if sid:
                invoiced_by[sid] += inv.amount_total_signed
                invoiced_ids[sid].append(inv.id)

        # Cartera vencida total a HOY: facturas no pagadas (o parciales) cuyo
        # vencimiento ya pasó, sin acotar al periodo del panel.
        overdue_by, overdue_ids = defaultdict(float), defaultdict(list)
        for inv in invoice_model.search(base + [
            ("payment_state", "in", ("not_paid", "partial")),
            ("invoice_date_due", "!=", False),
            ("invoice_date_due", "<", today.isoformat()),
        ]):
            sid = _seller_of(inv)
            if sid:
                overdue_by[sid] += inv.amount_residual
                overdue_ids[sid].append(inv.id)

        return invoiced_by, invoiced_ids, overdue_by, overdue_ids

    @api.model
    def _sfa_target_by_user(self, user_ids, month_start, month_end, allowed_company_ids):
        """Suma de objetivos por vendedor en el rango de meses del periodo.
        period='month' → 1 mes; period='year' → 12 meses (date_month normalizada a día 1)."""
        targets = self.env["sales.field.target"].sudo().search([
            ("user_id", "in", user_ids),
            ("date_month", ">=", month_start.replace(day=1).isoformat()),
            ("date_month", "<=", month_end.isoformat()),
            ("company_id", "in", allowed_company_ids),
        ])
        by_user = defaultdict(float)
        for t in targets:
            by_user[t.user_id.id] += t.target_amount
        return by_user

    @staticmethod
    def _sfa_pct(paid, target):
        return round(paid / target * 100.0, 1) if target else 0.0

    @api.model
    def _sfa_extend_dashboard(self, result, dashboard_user, month_start, month_end, seller_ids):
        """Inyecta el KPI 'Facturado Pagado' en el dict del dashboard.

        Se llama desde el core tras construir `result`. Muta `result` in-place:
        marca has_account=True, agrega la tarjeta del vendedor y, si es vista
        gerencial, los importes por vendedor + el total del equipo."""
        result = super()._sfa_extend_dashboard(result, dashboard_user, month_start, month_end, seller_ids)
        result["has_account"] = True

        invoice_model = self.env["account.move"]
        allowed_company_ids = self.env.companies.ids
        period_suffix = result.get("period_suffix", _("del Mes"))

        # why: la fecha real de pago se reconstruye desde reconciles, asi que no
        # podemos filtrar el mes en SQL. Pero descartamos facturas viejas: una
        # emitida hace > N dias rara vez se paga dentro del mes consultado.
        lookback = self._sfa_invoice_lookback_days()
        invoice_date_floor = (month_start - timedelta(days=lookback)).isoformat()

        # ---- Tarjeta del vendedor ----
        invoice_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
            ("company_id", "in", allowed_company_ids),
            ("invoice_date", ">=", invoice_date_floor),
            # Clientes excluidos del seguimiento no cuentan en el KPI.
            ("partner_id.sfa_excluded", "=", False),
            "|",
            ("invoice_user_id", "=", dashboard_user.id),
            "&",
            ("invoice_user_id", "=", False),
            ("partner_id.user_id", "=", dashboard_user.id),
        ]
        paid_invoices = invoice_model.search(invoice_domain)
        paid_date_by_invoice = self._get_paid_date_by_invoice(paid_invoices)

        paid_invoice_ids_in_month = []
        paid_amount = 0.0
        for inv in paid_invoices:
            paid_date = paid_date_by_invoice.get(inv.id)
            if paid_date and month_start <= paid_date <= month_end:
                paid_invoice_ids_in_month.append(inv.id)
                paid_amount += inv.amount_total_signed

        result["kpis"]["paid_invoices_month_amount"] = round(paid_amount, 2)
        result["actions"]["paid_invoices_month_amount"] = self._sfa_window_action(
            _("Facturas Pagadas %(suffix)s") % {"suffix": period_suffix},
            "account.move", "list,form",
            [("id", "in", paid_invoice_ids_in_month), ("move_type", "=", "out_invoice")],
            context={"default_move_type": "out_invoice"},
        )

        # ---- Facturado / Vencido / Objetivo del vendedor ----
        today = fields.Date.context_today(self)
        inv_by, inv_ids, ovd_by, ovd_ids = self._sfa_compute_billing(
            [dashboard_user.id], allowed_company_ids, month_start, month_end, today
        )
        target_by = self._sfa_target_by_user(
            [dashboard_user.id], month_start, month_end, allowed_company_ids
        )
        invoiced_amount = round(inv_by.get(dashboard_user.id, 0.0), 2)
        overdue_amount = round(ovd_by.get(dashboard_user.id, 0.0), 2)
        target_amount = round(target_by.get(dashboard_user.id, 0.0), 2)
        result["kpis"]["invoiced_month_amount"] = invoiced_amount
        result["kpis"]["overdue_amount"] = overdue_amount
        result["kpis"]["target_amount"] = target_amount
        result["kpis"]["target_pct"] = self._sfa_pct(paid_amount, target_amount)

        result["actions"]["invoiced_month_amount"] = self._sfa_window_action(
            _("Facturado %(suffix)s") % {"suffix": period_suffix},
            "account.move", "list,form",
            [("id", "in", inv_ids.get(dashboard_user.id, [])), ("move_type", "=", "out_invoice")],
            context={"default_move_type": "out_invoice"},
        )
        result["actions"]["overdue_amount"] = self._sfa_window_action(
            _("Cartera Vencida"),
            "account.move", "list,form",
            [("id", "in", ovd_ids.get(dashboard_user.id, [])), ("move_type", "=", "out_invoice")],
            context={"default_move_type": "out_invoice"},
        )

        # ---- Desglose gerencial por vendedor ----
        manager = result.get("manager") or {}
        if not (result.get("is_manager") and manager.get("enabled") and seller_ids):
            return result

        team_invoice_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
            ("company_id", "in", allowed_company_ids),
            ("invoice_date", ">=", invoice_date_floor),
            ("partner_id.sfa_excluded", "=", False),
            "|",
            ("invoice_user_id", "in", seller_ids),
            "&",
            ("invoice_user_id", "=", False),
            ("partner_id.user_id", "in", seller_ids),
        ]
        team_paid_invoices = invoice_model.search(team_invoice_domain)
        team_paid_dates = self._get_paid_date_by_invoice(team_paid_invoices)

        paid_amount_by_user = defaultdict(float)
        paid_invoice_ids_by_user = defaultdict(list)
        for inv in team_paid_invoices:
            paid_date = team_paid_dates.get(inv.id)
            if not paid_date or not (month_start <= paid_date <= month_end):
                continue
            seller = inv.invoice_user_id or inv.partner_id.user_id
            if not seller or seller.id not in seller_ids:
                continue
            paid_amount_by_user[seller.id] += inv.amount_total_signed
            paid_invoice_ids_by_user[seller.id].append(inv.id)

        # Facturado / Vencido / Objetivo de TODO el equipo, en una pasada.
        team_inv_by, team_inv_ids, team_ovd_by, team_ovd_ids = self._sfa_compute_billing(
            seller_ids, allowed_company_ids, month_start, month_end, today
        )
        team_target_by = self._sfa_target_by_user(
            seller_ids, month_start, month_end, allowed_company_ids
        )

        def _seller_move_action(name, ids):
            return self._sfa_window_action(
                name, "account.move", "list,form",
                [("id", "in", ids), ("move_type", "=", "out_invoice")],
                context={"default_move_type": "out_invoice"},
            )

        for row in manager.get("sellers_summary", []):
            seller_id = row["seller_id"]
            seller_name = row.get("seller_name") or ""
            row["paid_amount"] = round(paid_amount_by_user.get(seller_id, 0.0), 2)
            row["invoiced_amount"] = round(team_inv_by.get(seller_id, 0.0), 2)
            row["overdue_amount"] = round(team_ovd_by.get(seller_id, 0.0), 2)
            row["target_amount"] = round(team_target_by.get(seller_id, 0.0), 2)
            row["target_pct"] = self._sfa_pct(row["paid_amount"], row["target_amount"])

            paid_action_key = f"manager_seller_paid_{seller_id}"
            invoiced_action_key = f"manager_seller_invoiced_{seller_id}"
            overdue_action_key = f"manager_seller_overdue_{seller_id}"
            row["paid_action_key"] = paid_action_key
            row["invoiced_action_key"] = invoiced_action_key
            row["overdue_action_key"] = overdue_action_key
            result["actions"][paid_action_key] = _seller_move_action(
                _("Facturas Pagadas %(suffix)s - %(seller)s") % {"suffix": period_suffix, "seller": seller_name},
                paid_invoice_ids_by_user.get(seller_id, []),
            )
            result["actions"][invoiced_action_key] = _seller_move_action(
                _("Facturado %(suffix)s - %(seller)s") % {"suffix": period_suffix, "seller": seller_name},
                team_inv_ids.get(seller_id, []),
            )
            result["actions"][overdue_action_key] = _seller_move_action(
                _("Cartera Vencida - %(seller)s") % {"seller": seller_name},
                team_ovd_ids.get(seller_id, []),
            )

        sellers = manager.get("sellers_summary", [])
        team_paid = round(sum(r.get("paid_amount", 0.0) for r in sellers), 2)
        team_target = round(sum(r.get("target_amount", 0.0) for r in sellers), 2)
        manager["kpis"]["team_paid_amount"] = team_paid
        manager["kpis"]["team_invoiced_amount"] = round(sum(r.get("invoiced_amount", 0.0) for r in sellers), 2)
        manager["kpis"]["team_overdue_amount"] = round(sum(r.get("overdue_amount", 0.0) for r in sellers), 2)
        manager["kpis"]["team_target_amount"] = team_target
        manager["kpis"]["team_target_pct"] = self._sfa_pct(team_paid, team_target)
        return result
