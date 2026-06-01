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
    def _get_year_range(self, date_ref):
        """Rango del año completo del date_ref (1-enero a 31-diciembre)."""
        if isinstance(date_ref, datetime):
            date_ref = date_ref.date()
        if not isinstance(date_ref, date):
            date_ref = fields.Date.to_date(date_ref)
        year_start = date(date_ref.year, 1, 1)
        year_end = date(date_ref.year, 12, 31)
        return year_start, year_end

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
    def get_dashboard_data(self, date_ref=False, target_user_id=False, period="month"):
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

        # Bug fix 2026-05-26: el periodo filtrado y "hoy" son independientes.
        # Antes: today = date_ref → cuando el frontend pasaba "2026-05-01" para
        # filtrar el mes, las listas Hoy/Atrasadas/Pendientes calculaban contra
        # 2026-05-01 en vez de la fecha real → "para hoy" siempre vacio.
        #
        # period='month' (default): KPIs muestran metricas del mes elegido.
        # period='year': KPIs muestran metricas del año completo elegido.
        # En ambos casos las listas operativas Hoy/Semana/Atrasadas usan today real.
        period_ref = fields.Date.to_date(date_ref) if date_ref else fields.Date.context_today(self)
        if period == "year":
            month_start, month_end = self._get_year_range(period_ref)
        else:
            period = "month"  # defensive: cualquier valor desconocido cae a month
            month_start, month_end = self._get_month_range(period_ref)
        today = fields.Date.context_today(self)

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

        # Coherencia con Facturado Pagado: cotizaciones de clientes excluidos
        # (Mercado Libre, empresas internas, autoservicio) no cuentan como
        # productividad del vendedor.
        quotations_month = sale_order_model.search_count(
            [
                ("user_id", "=", dashboard_user.id),
                ("state", "in", ["draft", "sent"]),
                ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                ("partner_id.x_sfa_excluded", "=", False),
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
            # Clientes excluidos del seguimiento (Mercado Libre, empresas internas,
            # autoservicio) NO cuentan en el KPI "Facturado Pagado del Mes" — su
            # operacion no la atiende el vendedor de campo y distorsiona el indicador.
            ("partner_id.x_sfa_excluded", "=", False),
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

        # S-02: "ultima interaccion por cliente" via DISTINCT ON. Una interaccion solo
        # cuenta como "pendiente/atrasada" si es la mas reciente del cliente con ese
        # vendedor. Las interacciones viejas con next_action_date pasado quedan saldadas
        # automaticamente cuando el vendedor registra una nueva del mismo cliente.
        #
        # JOIN res_partner para excluir clientes marcados x_sfa_excluded — no deben
        # aparecer en las listas operativas Hoy/Semana/Atrasados aunque tengan
        # interacciones historicas con next_action_date pendiente.
        self.env.cr.execute(
            """
            SELECT DISTINCT ON (si.partner_id) si.id
            FROM sales_interaction si
            JOIN res_partner p ON p.id = si.partner_id
            WHERE si.user_id = %s
              AND si.partner_id IS NOT NULL
              AND COALESCE(p.x_sfa_excluded, FALSE) = FALSE
            ORDER BY si.partner_id, si.interaction_datetime DESC, si.id DESC
            """,
            (dashboard_user.id,),
        )
        latest_ids = [row[0] for row in self.env.cr.fetchall()]

        # S-02: "atrasadas" = ultima del cliente con next_action_date < hoy.
        # Las anteriores quedan saldadas implicitamente porque ya existe una mas nueva.
        overdue_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", "<", today),
            ],
            ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"],
            order="next_action_date asc",
            limit=15,
        )

        # S-03: pendientes para HOY y para los proximos 7 dias. Mismo criterio
        # (solo la ultima del cliente cuenta) para no inflar las listas.
        week_end = today + timedelta(days=7)
        due_today_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", "=", today),
            ],
            ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"],
            order="partner_id",
            limit=20,
        )
        due_week_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", ">", today),
                ("next_action_date", "<=", week_end),
            ],
            ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"],
            order="next_action_date asc",
            limit=20,
        )

        assigned_partners = partner_model.search(
            [
                ("user_id", "=", dashboard_user.id),
                ("x_sfa_excluded", "=", False),
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

        # Sufijo dinamico segun periodo: "del Mes" para month, "del Año" para year.
        # Aparece en los titulos de las pantallas de detalle (al tocar una card).
        period_suffix = "del Año" if period == "year" else "del Mes"

        actions = {
            "total_interactions": _interaction_action(name=f"Interacciones {period_suffix}"),
            "visit": _interaction_action([("interaction_type", "=", "visit")], f"Visitas {period_suffix}"),
            "call": _interaction_action([("interaction_type", "=", "call")], f"Llamadas {period_suffix}"),
            "whatsapp": _interaction_action([("interaction_type", "=", "whatsapp")], f"WhatsApp {period_suffix}"),
            "followup": _interaction_action([("interaction_type", "=", "followup")], f"Seguimientos {period_suffix}"),
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
                "name": f"Mis Cotizaciones {period_suffix}",
                "res_model": "sale.order",
                "view_mode": "list,form,kanban",
                "views": _views_from_mode("list,form,kanban"),
                "target": "current",
                "domain": [
                    ("user_id", "=", dashboard_user.id),
                    ("state", "in", ["draft", "sent"]),
                    ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                    # Coherente con el KPI: la lista abierta desde la card
                    # tampoco muestra cotizaciones de clientes excluidos.
                    ("partner_id.x_sfa_excluded", "=", False),
                ],
            },
            "paid_invoices_month_amount": {
                "type": "ir.actions.act_window",
                "name": f"Facturas Pagadas {period_suffix}",
                "res_model": "account.move",
                "view_mode": "list,form",
                "views": _views_from_mode("list,form"),
                "target": "current",
                # Agregar move_type al domain hace que Odoo elija la vista de
                # "Facturas de Cliente" (que incluye partner_id como columna)
                # en lugar de la vista generica de account.move (sin partner).
                # default_move_type en el context refuerza el comportamiento.
                "domain": [
                    ("id", "in", paid_invoice_ids_in_month),
                    ("move_type", "=", "out_invoice"),
                ],
                "context": {"default_move_type": "out_invoice"},
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
            # S-02: action_overdue usa latest_ids para coincidir con la lista del dashboard.
            "overdue": {
                "type": "ir.actions.act_window",
                "name": "Interacciones Atrasadas",
                "res_model": "sales.interaction",
                "view_mode": "list,kanban,form,calendar",
                "views": _views_from_mode("list,kanban,form,calendar"),
                "target": "current",
                "domain": [("id", "in", latest_ids), ("next_action_date", "<", today)],
            },
            # S-03: pendientes hoy / esta semana — mismo criterio (ultima del cliente).
            "due_today": {
                "type": "ir.actions.act_window",
                "name": "Pendientes para Hoy",
                "res_model": "sales.interaction",
                "view_mode": "list,kanban,form,calendar",
                "views": _views_from_mode("list,kanban,form,calendar"),
                "target": "current",
                "domain": [("id", "in", latest_ids), ("next_action_date", "=", today)],
            },
            "due_this_week": {
                "type": "ir.actions.act_window",
                "name": "Pendientes Esta Semana",
                "res_model": "sales.interaction",
                "view_mode": "list,kanban,form,calendar",
                "views": _views_from_mode("list,kanban,form,calendar"),
                "target": "current",
                "domain": [
                    ("id", "in", latest_ids),
                    ("next_action_date", ">", today),
                    ("next_action_date", "<=", week_end),
                ],
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
                        # Mismo criterio que en la vista del vendedor.
                        ("partner_id.x_sfa_excluded", "=", False),
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
                    # Mismo criterio que en la vista del vendedor: las facturas de
                    # clientes excluidos del seguimiento no cuentan en el "Facturado
                    # Pagado del Equipo" ni en el desglose por vendedor.
                    ("partner_id.x_sfa_excluded", "=", False),
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
                        "name": f"Interacciones {period_suffix} - {seller.name}",
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
                        "name": f"Cotizaciones {period_suffix} - {seller.name}",
                        "res_model": "sale.order",
                        "view_mode": "list,form,kanban",
                        "views": _views_from_mode("list,form,kanban"),
                        "target": "current",
                        "domain": [
                            ("user_id", "=", seller.id),
                            ("state", "in", ["draft", "sent"]),
                            ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                            ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                            ("partner_id.x_sfa_excluded", "=", False),
                        ],
                    }
                    actions[paid_action_key] = {
                        "type": "ir.actions.act_window",
                        "name": f"Facturas Pagadas {period_suffix} - {seller.name}",
                        "res_model": "account.move",
                        "view_mode": "list,form",
                        "views": _views_from_mode("list,form"),
                        "target": "current",
                        "domain": [
                            ("id", "in", paid_invoice_ids_by_user.get(seller.id, [])),
                            ("move_type", "=", "out_invoice"),
                        ],
                        "context": {"default_move_type": "out_invoice"},
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
            "period": period,
            "period_suffix": period_suffix,
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
                "due_today": due_today_interactions,
                "due_this_week": due_week_interactions,
                "inactive_partners": no_interaction_30,
            },
            "actions": actions,
            "currency": {
                "symbol": self.env.company.currency_id.symbol,
                "position": self.env.company.currency_id.position,
            },
            "manager": manager_data,
        }
