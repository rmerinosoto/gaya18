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

from odoo import _, api, models


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
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "sales_field_sfa.invoice_lookback_days"
        )
        try:
            return int(raw) if int(raw) > 0 else 90
        except (TypeError, ValueError):
            return 90

    @staticmethod
    def _views_from_mode(view_mode):
        return [[False, view.strip()] for view in view_mode.split(",") if view.strip()]

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
        result["actions"]["paid_invoices_month_amount"] = {
            "type": "ir.actions.act_window",
            "name": _("Facturas Pagadas %(suffix)s") % {"suffix": period_suffix},
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": self._views_from_mode("list,form"),
            "target": "current",
            "domain": [
                ("id", "in", paid_invoice_ids_in_month),
                ("move_type", "=", "out_invoice"),
            ],
            "context": {"default_move_type": "out_invoice"},
        }

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

        for row in manager.get("sellers_summary", []):
            seller_id = row["seller_id"]
            paid_action_key = f"manager_seller_paid_{seller_id}"
            row["paid_amount"] = round(paid_amount_by_user.get(seller_id, 0.0), 2)
            row["paid_action_key"] = paid_action_key
            result["actions"][paid_action_key] = {
                "type": "ir.actions.act_window",
                "name": _("Facturas Pagadas %(suffix)s - %(seller)s") % {
                    "suffix": period_suffix,
                    "seller": row.get("seller_name") or "",
                },
                "res_model": "account.move",
                "view_mode": "list,form",
                "views": self._views_from_mode("list,form"),
                "target": "current",
                "domain": [
                    ("id", "in", paid_invoice_ids_by_user.get(seller_id, [])),
                    ("move_type", "=", "out_invoice"),
                ],
                "context": {"default_move_type": "out_invoice"},
            }

        manager["kpis"]["team_paid_amount"] = round(
            sum(row.get("paid_amount", 0.0) for row in manager.get("sellers_summary", [])), 2
        )
        return result
