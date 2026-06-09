from datetime import date, datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

# Campos que devuelven las listas operativas (Hoy/Atrasadas/Pendientes). Se
# define una vez para no repetir la lista en cada search_read.
_LIST_FIELDS = ["name", "partner_id", "interaction_type", "interaction_datetime", "result", "next_action_date"]


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
    def _sfa_get_int_param(self, key, default):
        """Lee un parametro entero de ir.config_parameter con fallback robusto.
        Permite a cada empresa ajustar las ventanas temporales del dashboard
        (inactividad, horizonte semanal, etc) sin tocar codigo."""
        raw = self.env["ir.config_parameter"].sudo().get_param(key)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    @api.model
    def _sfa_views_from_mode(self, view_mode):
        """'list,form' → [[False,'list'],[False,'form']]. Centraliza la conversion
        view_mode→views que usan todas las acciones (core y modulo puente)."""
        return [[False, view.strip()] for view in view_mode.split(",") if view.strip()]

    @api.model
    def _sfa_day_bounds_utc(self, day):
        """Convierte un dia (date, interpretado en la TZ del usuario) a sus limites
        [inicio, fin] en UTC *naive*, listos para comparar contra columnas Datetime
        (Odoo las almacena en UTC). Sin esto, en zonas != UTC (Gaya = America/Mexico_City,
        UTC-6) las interacciones cercanas a medianoche caian en el mes/dia contiguo."""
        tz = pytz.timezone(self.env.user.tz or "UTC")
        start_local = tz.localize(datetime.combine(day, time.min))
        end_local = tz.localize(datetime.combine(day, time.max))
        return (
            start_local.astimezone(pytz.utc).replace(tzinfo=None),
            end_local.astimezone(pytz.utc).replace(tzinfo=None),
        )

    @api.model
    def _sfa_window_action(self, name, res_model, view_mode, domain, context=None):
        """Factory de acciones ir.actions.act_window. Evita repetir el mismo dict
        (type/views/target) en cada card y lista del dashboard."""
        action = {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": view_mode,
            "views": self._sfa_views_from_mode(view_mode),
            "target": "current",
            "domain": domain,
        }
        if context is not None:
            action["context"] = context
        return action

    @api.model
    def _sfa_extend_dashboard(self, result, dashboard_user, month_start, month_end, seller_ids):
        """Seam de extension para modulos puente (p.ej. sales_field_sfa_account).

        El core NO depende de `account`. El KPI "Facturado Pagado" y los importes
        por vendedor los inyecta el modulo puente sobreescribiendo este metodo.
        Recibe el dict `result` ya construido y lo muta in-place. En el core es un
        no-op; `result['has_account']` queda en False y el frontend oculta las
        tarjetas de facturacion."""
        return result

    # ------------------------------------------------------------------
    # Helpers privados de get_dashboard_data. Cada uno cubre una seccion
    # cohesiva (usuario, KPIs, listas, acciones, gerencia) para que el
    # metodo publico quede como simple orquestador.
    # ------------------------------------------------------------------

    @api.model
    def _sfa_resolve_dashboard_user(self, is_manager, target_user_id, allowed_company_ids):
        """Resuelve sobre que vendedor se calculan los datos. Un gerente puede
        inspeccionar el dashboard de otro vendedor (target_user_id) siempre que
        sea interno, activo y comparta al menos una compañia permitida; cualquier
        otro caso cae al usuario actual."""
        dashboard_user = self.env.user
        if is_manager and target_user_id:
            candidate_user = self.env["res.users"].browse(int(target_user_id)).exists()
            if (
                candidate_user
                and not candidate_user.share
                and candidate_user.active
                and set(candidate_user.company_ids.ids or [candidate_user.company_id.id]) & set(allowed_company_ids)
            ):
                dashboard_user = candidate_user
        return dashboard_user

    @api.model
    def _sfa_compute_kpis(self, dashboard_user, interaction_month_domain, month_start_dt, month_end_dt, valid_results):
        """KPIs del periodo (tarjetas superiores) para el vendedor seleccionado."""
        interaction_model = self.env["sales.interaction"]
        sale_order_model = self.env["sale.order"]

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

        # Prospecto/Cliente ya no se filtran por el `code` literal del catalogo,
        # sino por las banderas semanticas is_prospect/is_customer. Asi otra empresa
        # puede renombrar o reordenar sus estados sin romper estos KPIs.
        prospect_contacted = interaction_model.search_count(
            interaction_month_domain
            + [
                ("partner_id.sfa_customer_status.is_prospect", "=", True),
                ("result", "in", valid_results),
            ]
        )
        customer_contacted = interaction_model.search_count(
            interaction_month_domain
            + [
                ("partner_id.sfa_customer_status.is_customer", "=", True),
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
                ("partner_id.sfa_excluded", "=", False),
            ]
        )

        return {
            "total_interactions": total_interactions,
            "visit": type_counts.get("visit", 0),
            "call": type_counts.get("call", 0),
            "whatsapp": type_counts.get("whatsapp", 0),
            "followup": type_counts.get("followup", 0),
            "prospect_contacted": prospect_contacted,
            "customer_contacted": customer_contacted,
            "quotations_month": quotations_month,
        }

    @api.model
    def _sfa_compute_latest_interaction_ids(self, dashboard_user):
        """S-02: "ultima interaccion por cliente" via DISTINCT ON. Una interaccion solo
        cuenta como "pendiente/atrasada" si es la mas reciente del cliente con ese
        vendedor. Las interacciones viejas con next_action_date pasado quedan saldadas
        automaticamente cuando el vendedor registra una nueva del mismo cliente.

        JOIN res_partner para excluir clientes marcados sfa_excluded — no deben
        aparecer en las listas operativas Hoy/Semana/Atrasados aunque tengan
        interacciones historicas con next_action_date pendiente."""
        self.env.cr.execute(
            """
            SELECT DISTINCT ON (si.partner_id) si.id
            FROM sales_interaction si
            JOIN res_partner p ON p.id = si.partner_id
            WHERE si.user_id = %s
              AND si.partner_id IS NOT NULL
              AND COALESCE(p.sfa_excluded, FALSE) = FALSE
            ORDER BY si.partner_id, si.interaction_datetime DESC, si.id DESC
            """,
            (dashboard_user.id,),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _sfa_compute_inactive_partners(self, dashboard_user, allowed_company_ids, inactivity_days):
        """Clientes asignados al vendedor sin interaccion en `inactivity_days` dias.

        NOTA (cap): solo evalua los primeros 200 partners asignados y devuelve a lo
        sumo 30, suficiente para la lista operativa del dashboard. Si un vendedor
        supera ese volumen la lista es indicativa, no exhaustiva."""
        interaction_model = self.env["sales.interaction"]
        partner_model = self.env["res.partner"]

        assigned_partners = partner_model.search(
            [
                ("user_id", "=", dashboard_user.id),
                ("sfa_excluded", "=", False),
                "|",
                ("company_id", "=", False),
                ("company_id", "in", allowed_company_ids),
            ]
        )
        inactive = []
        if not assigned_partners:
            return inactive

        # _read_group (API 18) devuelve (partner_record, max_datetime) ya tipados.
        # Filtra por dashboard_user: la inactividad se mide contra las interacciones
        # del vendedor DUEÑO, no las de cualquier vendedor (decision 2026-06-09). Un
        # cliente sin contacto propio aparece como inactivo aunque otro lo haya visto.
        last_by_partner = {
            partner.id: last_dt
            for partner, last_dt in interaction_model._read_group(
                [
                    ("partner_id", "in", assigned_partners.ids),
                    ("user_id", "=", dashboard_user.id),
                ],
                groupby=["partner_id"],
                aggregates=["interaction_datetime:max"],
            )
            if partner and last_dt
        }
        threshold = fields.Datetime.now() - timedelta(days=inactivity_days)
        for partner in assigned_partners[:200]:
            last_dt = last_by_partner.get(partner.id)
            if not last_dt or last_dt < threshold:
                inactive.append(
                    {
                        "id": partner.id,
                        "name": partner.display_name,
                        "phone": partner.phone,
                        "mobile": partner.mobile,
                        "last_interaction": last_dt.strftime("%Y-%m-%d %H:%M:%S") if last_dt else False,
                    }
                )
            if len(inactive) >= 30:
                break
        return inactive

    @api.model
    def _sfa_compute_operational_lists(self, dashboard_user, today, allowed_company_ids):
        """Listas operativas del dia a dia (Hoy / Atrasadas / Pendientes / Sin contacto).

        Devuelve (lists, ctx): `lists` es el bloque que consume el frontend; `ctx`
        lleva los escalares (latest_ids, ventanas) que necesita _sfa_build_actions
        para que las pantallas de detalle coincidan exactamente con cada lista."""
        interaction_model = self.env["sales.interaction"]

        # Ventanas temporales configurables por empresa (ir.config_parameter).
        # Defaults = comportamiento historico de Gaya. Otra empresa las ajusta
        # desde Seguimiento Comercial → Configuración → Ajustes.
        inactivity_days = self._sfa_get_int_param("sales_field_sfa.inactivity_days", 30)
        week_horizon_days = self._sfa_get_int_param("sales_field_sfa.week_horizon_days", 7)

        # Limites de "hoy" en UTC naive segun la TZ del usuario (ver _sfa_day_bounds_utc).
        today_start_dt, today_end_dt = self._sfa_day_bounds_utc(today)

        interactions_today = interaction_model.search_read(
            [
                ("user_id", "=", dashboard_user.id),
                ("interaction_datetime", ">=", fields.Datetime.to_string(today_start_dt)),
                ("interaction_datetime", "<=", fields.Datetime.to_string(today_end_dt)),
            ],
            _LIST_FIELDS,
            order="interaction_datetime asc",
            limit=15,
        )

        latest_ids = self._sfa_compute_latest_interaction_ids(dashboard_user)

        # S-02: "atrasadas" = ultima del cliente con next_action_date < hoy.
        # Las anteriores quedan saldadas implicitamente porque ya existe una mas nueva.
        overdue_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", "<", today),
            ],
            _LIST_FIELDS,
            order="next_action_date asc",
            limit=15,
        )

        # S-03: pendientes para HOY y para los proximos N dias (config, default 7).
        # Mismo criterio (solo la ultima del cliente cuenta) para no inflar las listas.
        week_end = today + timedelta(days=week_horizon_days)
        due_today_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", "=", today),
            ],
            _LIST_FIELDS,
            order="partner_id",
            limit=20,
        )
        due_week_interactions = interaction_model.search_read(
            [
                ("id", "in", latest_ids),
                ("next_action_date", ">", today),
                ("next_action_date", "<=", week_end),
            ],
            _LIST_FIELDS,
            order="next_action_date asc",
            limit=20,
        )

        inactive_partners = self._sfa_compute_inactive_partners(dashboard_user, allowed_company_ids, inactivity_days)

        lists = {
            "interactions_today": interactions_today,
            "overdue": overdue_interactions,
            "due_today": due_today_interactions,
            "due_this_week": due_week_interactions,
            "inactive_partners": inactive_partners,
        }
        ctx = {
            "latest_ids": latest_ids,
            "today_start_dt": today_start_dt,
            "today_end_dt": today_end_dt,
            "week_end": week_end,
            "inactivity_days": inactivity_days,
            "inactive_partner_ids": [p["id"] for p in inactive_partners],
        }
        return lists, ctx

    @api.model
    def _sfa_build_actions(self, dashboard_user, interaction_month_domain, month_start_dt,
                           month_end_dt, today, valid_results, period_suffix, ctx):
        """Construye el dict de acciones (act_window) que abre cada card/lista del
        dashboard al pulsarla. `ctx` viene de _sfa_compute_operational_lists para que
        cada pantalla de detalle coincida con su lista (mismos latest_ids/ventanas)."""
        latest_ids = ctx["latest_ids"]
        today_start_dt = ctx["today_start_dt"]
        today_end_dt = ctx["today_end_dt"]
        week_end = ctx["week_end"]
        inactivity_days = ctx["inactivity_days"]

        def _interaction_action(extra_domain=None, name="Interacciones"):
            domain = list(interaction_month_domain)
            if extra_domain:
                domain.extend(extra_domain)
            return self._sfa_window_action(name, "sales.interaction", "kanban,list,calendar,form", domain)

        quotation_month_domain = [
            ("user_id", "=", dashboard_user.id),
            ("state", "in", ["draft", "sent"]),
            ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
            ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
            # Coherente con el KPI: la lista abierta desde la card tampoco
            # muestra cotizaciones de clientes excluidos.
            ("partner_id.sfa_excluded", "=", False),
        ]
        today_domain = [
            ("user_id", "=", dashboard_user.id),
            ("interaction_datetime", ">=", fields.Datetime.to_string(today_start_dt)),
            ("interaction_datetime", "<=", fields.Datetime.to_string(today_end_dt)),
        ]

        return {
            "total_interactions": _interaction_action(name=_("Interacciones %(suffix)s") % {"suffix": period_suffix}),
            "visit": _interaction_action([("interaction_type", "=", "visit")], _("Visitas %(suffix)s") % {"suffix": period_suffix}),
            "call": _interaction_action([("interaction_type", "=", "call")], _("Llamadas %(suffix)s") % {"suffix": period_suffix}),
            "whatsapp": _interaction_action([("interaction_type", "=", "whatsapp")], _("WhatsApp %(suffix)s") % {"suffix": period_suffix}),
            "followup": _interaction_action([("interaction_type", "=", "followup")], _("Seguimientos %(suffix)s") % {"suffix": period_suffix}),
            "prospect_contacted": _interaction_action(
                [
                    ("partner_id.sfa_customer_status.is_prospect", "=", True),
                    ("result", "in", valid_results),
                ],
                _("Prospectos Contactados"),
            ),
            "customer_contacted": _interaction_action(
                [
                    ("partner_id.sfa_customer_status.is_customer", "=", True),
                    ("result", "in", valid_results),
                ],
                _("Clientes Contactados"),
            ),
            "quotations_month": self._sfa_window_action(
                _("Mis Cotizaciones %(suffix)s") % {"suffix": period_suffix},
                "sale.order", "list,form,kanban", quotation_month_domain,
            ),
            "interactions_today": self._sfa_window_action(
                _("Interacciones de Hoy"), "sales.interaction", "list,kanban,form,calendar", today_domain,
            ),
            # S-02: action_overdue usa latest_ids para coincidir con la lista del dashboard.
            "overdue": self._sfa_window_action(
                _("Interacciones Atrasadas"), "sales.interaction", "list,kanban,form,calendar",
                [("id", "in", latest_ids), ("next_action_date", "<", today)],
            ),
            # S-03: pendientes hoy / esta semana — mismo criterio (ultima del cliente).
            "due_today": self._sfa_window_action(
                _("Pendientes para Hoy"), "sales.interaction", "list,kanban,form,calendar",
                [("id", "in", latest_ids), ("next_action_date", "=", today)],
            ),
            "due_this_week": self._sfa_window_action(
                _("Pendientes Esta Semana"), "sales.interaction", "list,kanban,form,calendar",
                [
                    ("id", "in", latest_ids),
                    ("next_action_date", ">", today),
                    ("next_action_date", "<=", week_end),
                ],
            ),
            "inactive_partners": self._sfa_window_action(
                _("Clientes sin Interacción (%(days)s días)") % {"days": inactivity_days},
                "res.partner", "list,form,kanban",
                [("id", "in", ctx["inactive_partner_ids"])],
            ),
        }

    @api.model
    def _sfa_compute_manager_data(self, is_manager, allowed_company_ids, month_start_dt,
                                  month_end_dt, period_suffix, actions):
        """Bloque gerencial: resumen por vendedor + KPIs de equipo. Muta `actions`
        in-place para agregar las acciones por vendedor (interacciones/cotizaciones).
        Devuelve (manager_data, user_options); en no-gerentes ambos van vacios."""
        if not is_manager:
            return {"enabled": False, "kpis": {}, "sellers_summary": []}, []

        interaction_model = self.env["sales.interaction"]
        sale_order_model = self.env["sale.order"]

        manager_data = {
            "enabled": True,
            "kpis": {
                "team_sellers": 0,
                "team_active_sellers": 0,
                "team_interactions": 0,
                "team_quotations": 0,
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
        if not seller_ids:
            return manager_data, user_options

        interactions_by_user = {
            seller.id: count
            for seller, count in interaction_model._read_group(
                [
                    ("user_id", "in", seller_ids),
                    ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
                ],
                groupby=["user_id"],
                aggregates=["__count"],
            )
            if seller
        }

        quotations_by_user = {
            seller.id: count
            for seller, count in sale_order_model._read_group(
                [
                    ("user_id", "in", seller_ids),
                    ("state", "in", ["draft", "sent"]),
                    ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                    # Mismo criterio que en la vista del vendedor.
                    ("partner_id.sfa_excluded", "=", False),
                ],
                groupby=["user_id"],
                aggregates=["__count"],
            )
            if seller
        }

        sellers_summary = []
        for seller in sales_users.sorted(key=lambda u: u.name or ""):
            interaction_count = interactions_by_user.get(seller.id, 0)
            quotation_count = quotations_by_user.get(seller.id, 0)

            interaction_action_key = f"manager_seller_interactions_{seller.id}"
            quotation_action_key = f"manager_seller_quotations_{seller.id}"

            actions[interaction_action_key] = self._sfa_window_action(
                _("Interacciones %(suffix)s - %(seller)s") % {"suffix": period_suffix, "seller": seller.name},
                "sales.interaction", "kanban,list,calendar,form",
                [
                    ("user_id", "=", seller.id),
                    ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
                ],
            )
            actions[quotation_action_key] = self._sfa_window_action(
                _("Cotizaciones %(suffix)s - %(seller)s") % {"suffix": period_suffix, "seller": seller.name},
                "sale.order", "list,form,kanban",
                [
                    ("user_id", "=", seller.id),
                    ("state", "in", ["draft", "sent"]),
                    ("create_date", ">=", fields.Datetime.to_string(month_start_dt)),
                    ("create_date", "<=", fields.Datetime.to_string(month_end_dt)),
                    ("partner_id.sfa_excluded", "=", False),
                ],
            )

            sellers_summary.append(
                {
                    "seller_id": seller.id,
                    "seller_name": seller.name,
                    "interactions": interaction_count,
                    "quotations": quotation_count,
                    "interaction_action_key": interaction_action_key,
                    "quotation_action_key": quotation_action_key,
                }
            )

        manager_data = {
            "enabled": True,
            "kpis": {
                "team_sellers": len(sellers_summary),
                "team_active_sellers": sum(1 for row in sellers_summary if row["interactions"] > 0),
                "team_interactions": sum(row["interactions"] for row in sellers_summary),
                "team_quotations": sum(row["quotations"] for row in sellers_summary),
            },
            "sellers_summary": sellers_summary,
        }
        return manager_data, user_options

    @api.model
    def get_dashboard_data(self, date_ref=False, target_user_id=False, period="month"):
        user = self.env.user
        is_manager = user.has_group("sales_field_sfa.group_sales_field_manager")
        allowed_company_ids = self.env.companies.ids

        dashboard_user = self._sfa_resolve_dashboard_user(is_manager, target_user_id, allowed_company_ids)

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

        # Limites del periodo en UTC naive (la TZ del usuario define donde empieza
        # y termina el dia local). Comparables directamente con columnas Datetime.
        month_start_dt = self._sfa_day_bounds_utc(month_start)[0]
        month_end_dt = self._sfa_day_bounds_utc(month_end)[1]

        interaction_month_domain = [
            ("user_id", "=", dashboard_user.id),
            ("interaction_datetime", ">=", fields.Datetime.to_string(month_start_dt)),
            ("interaction_datetime", "<=", fields.Datetime.to_string(month_end_dt)),
        ]
        valid_results = ["contacted", "interested", "quotation_sent", "order_taken"]

        kpis = self._sfa_compute_kpis(
            dashboard_user, interaction_month_domain, month_start_dt, month_end_dt, valid_results
        )
        lists, list_ctx = self._sfa_compute_operational_lists(dashboard_user, today, allowed_company_ids)

        # Sufijo dinamico segun periodo. Traducible: cada idioma lo resuelve via .po.
        # Aparece en los titulos de las pantallas de detalle (al tocar una card).
        period_suffix = _("del Año") if period == "year" else _("del Mes")

        actions = self._sfa_build_actions(
            dashboard_user, interaction_month_domain, month_start_dt, month_end_dt,
            today, valid_results, period_suffix, list_ctx,
        )
        manager_data, user_options = self._sfa_compute_manager_data(
            is_manager, allowed_company_ids, month_start_dt, month_end_dt, period_suffix, actions,
        )

        interaction_field = self.env["sales.interaction"]._fields
        result = {
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
            "kpis": kpis,
            "lists": lists,
            "actions": actions,
            "currency": {
                "symbol": self.env.company.currency_id.symbol,
                "position": self.env.company.currency_id.position,
            },
            "manager": manager_data,
            # El core no toca contabilidad. El modulo puente sales_field_sfa_account
            # pone has_account=True e inyecta el KPI "Facturado Pagado". El frontend
            # oculta las tarjetas de facturacion cuando has_account es falso.
            "has_account": False,
        }
        # Seam: el modulo puente (si esta instalado) muta result para agregar el
        # KPI de facturacion. seller_ids solo tiene sentido en vista gerencial.
        seller_ids = [row["seller_id"] for row in manager_data.get("sellers_summary", [])]
        self._sfa_extend_dashboard(result, dashboard_user, month_start, month_end, seller_ids)
        return result
