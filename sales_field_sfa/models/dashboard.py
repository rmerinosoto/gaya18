from collections import defaultdict
from datetime import date, datetime, time, timedelta

from odoo import api, fields, models


class SalesFieldDashboard(models.AbstractModel):
    _name = "sales.field.dashboard"
    _description = "Dashboard Seguimiento Comercial"

    @api.model
    def _get_month_range(self, date_ref):
        if isinstance(date_ref, datetime):
            date_ref = date_ref.date()
        if not isinstance(date_ref, date):
            date_ref = fields.Date.to_date(date_ref)

        month_start = date_ref.replace(day=1)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)
        month_end = next_month_start - timedelta(days=1)
        return month_start, month_end

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
    def get_dashboard_data(self, date_ref=False, target_user_id=False):
        user = self.env.user
        is_manager = user.has_group("sales_field_sfa.group_sales_field_manager")
        allowed_company_ids = self.env.companies.ids

        dashboard_user = user
        if is_manager and target_user_id:
            candidate_user = self.env["res.users"].browse(int(target_user_id)).exists()
            if (
                candidate_user
                and not candidate_user.share
                and candidate_user.active
                and set(candidate_user.company_ids.ids or [candidate_user.company_id.id]) & set(allowed_company_ids)
            ):
                dashboard_user = candidate_user

        today = fields.Date.to_date(date_ref) if date_ref else fields.Date.context_today(self)
        month_start, month_end = self._get_month_range(today)

        month_start_dt = datetime.combine(month_start, time.min)
        month_end_dt = datetime.combine(month_end, time.max)

        interaction_model = self.env["sales.interaction"]
        sale_order_model = self.env["sale.order"]
        partner_model = self.env["res.partner"]
        invoice_model = self.env["account.move"]

        interaction_month_domain = [
            ("user_id", "=", dashboard_user.id),
            ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
            ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
        ]

        valid_results = ["contacted", "interested", "quotation_sent", "order_taken"]

        # why: una sola query agrupada por interaction_type cubre total + 4 tipos.
        type_counts = {"visit": 0, "call": 0, "whatsapp": 0, "followup": 0}
        for itype, count in interaction_model._read_group(
            domain=interaction_month_domain,
            groupby=["interaction_type"],
            aggregates=["__count"],
        ):
            if itype in type_counts:
                type_counts[itype] = count
        total_interactions = sum(type_counts.values())
        prospect_contacted = interaction_model.search_count(
            interaction_month_domain
            + [
                ("partner_id.x_customer_status", "=", "prospect"),
                ("result", "in", valid_results),
            ]
        )
        customer_contacted = interaction_model.search_count(
            interaction_month_domain
            + [
                ("partner_id.x_customer_status", "=", "customer"),
                ("result", "in", valid_results),
            ]
        )

        quotations_month = sale_order_model.search_count(
            [
                ("user_id", "=", dashboard_user.id),
                ("state", "in", ["draft", "sent"]),
                ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
            ]
        )

        # why: la fecha real de pago se reconstruye desde reconciles, asi que no
        # podemos filtrar el mes en SQL. Pero descartamos facturas viejas: una
        # emitida hace >90 dias rara vez se paga dentro del mes consultado.
        invoice_date_floor = (month_start - timedelta(days=90)).isoformat()
        invoice_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
            ("company_id", "in", allowed_company_ids),
            ("invoice_date", ">=", invoice_date_floor),
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

        today_start_dt = datetime.combine(today, time.min)
        today_end_dt = datetime.combine(today, time.max)

        interactions_today = interaction_model.search_read(
            [
                ("user_id", "=", dashboard_user.id),
                ("interaction_datetime", ">=", fields.Datetime.to_string(today_start_dt)),
                ("interaction_datetime", "<=", fields.Datetime.to_string(today_end_dt)),
            ],
            ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"],
            order="interaction_datetime asc",
            limit=15,
        )

        overdue_interactions = interaction_model.search_read(
            [
                ("user_id", "=", dashboard_user.id),
                ("next_action_date", "<", today),
            ],
            ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"],
            order="next_action_date asc",
            limit=15,
        )

        assigned_partners = partner_model.search(
            [
                ("user_id", "=", dashboard_user.id),
                "|",
                ("company_id", "=", False),
                ("company_id", "in", allowed_company_ids),
            ]
        )
        no_interaction_30 = []
        if assigned_partners:
            grouped_last = interaction_model.read_group(
                [
                    ("partner_id", "in", assigned_partners.ids),
                ],
                ["partner_id", "interaction_datetime:max"],
                ["partner_id"],
                lazy=False,
            )
            last_by_partner = {
                item["partner_id"][0]: fields.Datetime.to_datetime(item["interaction_datetime_max"])
                for item in grouped_last
                if item.get("partner_id") and item.get("interaction_datetime_max")
            }
            threshold = fields.Datetime.now() - timedelta(days=30)
            for partner in assigned_partners[:200]:
                last_dt = last_by_partner.get(partner.id)
                if not last_dt or last_dt < threshold:
                    no_interaction_30.append(
                        {
                            "id": partner.id,
                            "name": partner.display_name,
                            "phone": partner.phone,
                            "mobile": partner.mobile,
                            "last_interaction": last_dt.strftime("%Y-%m-%d %H:%M:%S") if last_dt else False,
                        }
                    )
                if len(no_interaction_30) >= 30:
                    break

        def _views_from_mode(view_mode):
            return [[False, view.strip()] for view in view_mode.split(",") if view.strip()]

        def _interaction_action(extra_domain=None, name="Interacciones"):
            domain = list(interaction_month_domain)
            view_mode = "kanban,list,calendar,form"
            if extra_domain:
                domain.extend(extra_domain)
            return {
                "type": "ir.actions.act_window",
                "name": name,
                "res_model": "sales.interaction",
                "view_mode": view_mode,
                "views": _views_from_mode(view_mode),
                "target": "current",
                "domain": domain,
            }

        actions = {
            "total_interactions": _interaction_action(name="Interacciones del Mes"),
            "visit": _interaction_action([("interaction_type", "=", "visit")], "Visitas del Mes"),
            "call": _interaction_action([("interaction_type", "=", "call")], "Llamadas del Mes"),
            "whatsapp": _interaction_action([("interaction_type", "=", "whatsapp")], "WhatsApp del Mes"),
            "followup": _interaction_action([("interaction_type", "=", "followup")], "Seguimientos del Mes"),
            "prospect_contacted": _interaction_action(
                [
                    ("partner_id.x_customer_status", "=", "prospect"),
                    ("result", "in", valid_results),
                ],
                "Prospectos Contactados",
            ),
            "customer_contacted": _interaction_action(
                [
                    ("partner_id.x_customer_status", "=", "customer"),
                    ("result", "in", valid_results),
                ],
                "Clientes Contactados",
            ),
            "quotations_month": {
                "type": "ir.actions.act_window",
                "name": "Mis Cotizaciones del Mes",
                "res_model": "sale.order",
                "view_mode": "list,form,kanban",
                "views": _views_from_mode("list,form,kanban"),
                "target": "current",
                "domain": [
                    ("user_id", "=", dashboard_user.id),
                    ("state", "in", ["draft", "sent"]),
                    ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                ],
            },
            "paid_invoices_month_amount": {
                "type": "ir.actions.act_window",
                "name": "Facturas Pagadas del Mes",
                "res_model": "account.move",
                "view_mode": "list,form",
                "views": _views_from_mode("list,form"),
                "target": "current",
                "domain": [("id", "in", paid_invoice_ids_in_month)],
            },
            "interactions_today": {
                "type": "ir.actions.act_window",
                "name": "Interacciones de Hoy",
                "res_model": "sales.interaction",
                "view_mode": "list,kanban,form,calendar",
                "views": _views_from_mode("list,kanban,form,calendar"),
                "target": "current",
                "domain": [
                    ("user_id", "=", dashboard_user.id),
                    ("interaction_datetime", ">=", fields.Datetime.to_string(today_start_dt)),
                    ("interaction_datetime", "<=", fields.Datetime.to_string(today_end_dt)),
                ],
            },
            "overdue": {
                "type": "ir.actions.act_window",
                "name": "Interacciones Atrasadas",
                "res_model": "sales.interaction",
                "view_mode": "list,kanban,form,calendar",
                "views": _views_from_mode("list,kanban,form,calendar"),
                "target": "current",
                "domain": [("user_id", "=", dashboard_user.id), ("next_action_date", "<", today)],
            },
            "inactive_partners": {
                "type": "ir.actions.act_window",
                "name": "Clientes sin Interacción (30 días)",
                "res_model": "res.partner",
                "view_mode": "list,form,kanban",
                "views": _views_from_mode("list,form,kanban"),
                "target": "current",
                "domain": [("id", "in", [p["id"] for p in no_interaction_30])],
            },
        }

        manager_data = {"enabled": False, "kpis": {}, "sellers_summary": []}
        user_options = []
        if is_manager:
            manager_data = {
                "enabled": True,
                "kpis": {
                    "team_sellers": 0,
                    "team_active_sellers": 0,
                    "team_interactions": 0,
                    "team_quotations": 0,
                    "team_paid_amount": 0.0,
                },
                "sellers_summary": [],
            }
            group_user = self.env.ref("sales_field_sfa.group_sales_field_user")
            sales_users = self.env["res.users"].search(
                [
                    ("groups_id", "in", [group_user.id]),
                    ("share", "=", False),
                    ("active", "=", True),
                ]
            )
            sales_users = sales_users.filtered(
                lambda u: bool(set(u.company_ids.ids or [u.company_id.id]) & set(allowed_company_ids))
            )
            user_options = [{"id": u.id, "name": u.name} for u in sales_users.sorted(key=lambda x: x.name or "")]

            seller_ids = sales_users.ids
            if seller_ids:
                interactions_grouped = interaction_model.read_group(
                    [
                        ("user_id", "in", seller_ids),
                        ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
                        ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
                    ],
                    ["user_id"],
                    ["user_id"],
                    lazy=False,
                )
                interactions_by_user = {
                    item["user_id"][0]: item.get("__count", 0)
                    for item in interactions_grouped
                    if item.get("user_id")
                }

                quotations_grouped = sale_order_model.read_group(
                    [
                        ("user_id", "in", seller_ids),
                        ("state", "in", ["draft", "sent"]),
                        ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                        ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                    ],
                    ["user_id"],
                    ["user_id"],
                    lazy=False,
                )
                quotations_by_user = {
                    item["user_id"][0]: item.get("__count", 0)
                    for item in quotations_grouped
                    if item.get("user_id")
                }

                team_invoice_domain = [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "=", "paid"),
                    ("company_id", "in", allowed_company_ids),
                    ("invoice_date", ">=", invoice_date_floor),
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

                sellers_summary = []
                for seller in sales_users.sorted(key=lambda u: u.name or ""):
                    interaction_count = interactions_by_user.get(seller.id, 0)
                    quotation_count = quotations_by_user.get(seller.id, 0)
                    paid_amount_seller = round(paid_amount_by_user.get(seller.id, 0.0), 2)

                    interaction_action_key = f"manager_seller_interactions_{seller.id}"
                    quotation_action_key = f"manager_seller_quotations_{seller.id}"
                    paid_action_key = f"manager_seller_paid_{seller.id}"

                    actions[interaction_action_key] = {
                        "type": "ir.actions.act_window",
                        "name": f"Interacciones del Mes - {seller.name}",
                        "res_model": "sales.interaction",
                        "view_mode": "kanban,list,calendar,form",
                        "views": _views_from_mode("kanban,list,calendar,form"),
                        "target": "current",
                        "domain": [
                            ("user_id", "=", seller.id),
                            ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
                            ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
                        ],
                    }
                    actions[quotation_action_key] = {
                        "type": "ir.actions.act_window",
                        "name": f"Cotizaciones del Mes - {seller.name}",
                        "res_model": "sale.order",
                        "view_mode": "list,form,kanban",
                        "views": _views_from_mode("list,form,kanban"),
                        "target": "current",
                        "domain": [
                            ("user_id", "=", seller.id),
                            ("state", "in", ["draft", "sent"]),
                            ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                            ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                        ],
                    }
                    actions[paid_action_key] = {
                        "type": "ir.actions.act_window",
                        "name": f"Facturas Pagadas del Mes - {seller.name}",
                        "res_model": "account.move",
                        "view_mode": "list,form",
                        "views": _views_from_mode("list,form"),
                        "target": "current",
                        "domain": [("id", "in", paid_invoice_ids_by_user.get(seller.id, []))],
                    }

                    sellers_summary.append(
                        {
                            "seller_id": seller.id,
                            "seller_name": seller.name,
                            "interactions": interaction_count,
                            "quotations": quotation_count,
                            "paid_amount": paid_amount_seller,
                            "interaction_action_key": interaction_action_key,
                            "quotation_action_key": quotation_action_key,
                            "paid_action_key": paid_action_key,
                        }
                    )

                manager_data = {
                    "enabled": True,
                    "kpis": {
                        "team_sellers": len(sellers_summary),
                        "team_active_sellers": sum(1 for row in sellers_summary if row["interactions"] > 0),
                        "team_interactions": sum(row["interactions"] for row in sellers_summary),
                        "team_quotations": sum(row["quotations"] for row in sellers_summary),
                        "team_paid_amount": round(sum(row["paid_amount"] for row in sellers_summary), 2),
                    },
                    "sellers_summary": sellers_summary,
                }

        interaction_field = self.env["sales.interaction"]._fields
        return {
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
            "is_manager": is_manager,
            "selected_user": {"id": dashboard_user.id, "name": dashboard_user.name},
            "user_options": user_options,
            "labels": {
                "interaction_type": dict(interaction_field["interaction_type"]._description_selection(self.env)),
                "result": dict(interaction_field["result"]._description_selection(self.env)),
            },
            "kpis": {
                "total_interactions": total_interactions,
                "visit": type_counts.get("visit", 0),
                "call": type_counts.get("call", 0),
                "whatsapp": type_counts.get("whatsapp", 0),
                "followup": type_counts.get("followup", 0),
                "prospect_contacted": prospect_contacted,
                "customer_contacted": customer_contacted,
                "quotations_month": quotations_month,
                "paid_invoices_month_amount": round(paid_amount, 2),
            },
            "lists": {
                "interactions_today": interactions_today,
                "overdue": overdue_interactions,
                "inactive_partners": no_interaction_30,
            },
            "actions": actions,
            "currency": {
                "symbol": self.env.company.currency_id.symbol,
                "position": self.env.company.currency_id.position,
            },
            "manager": manager_data,
        }
