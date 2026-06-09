from datetime import date, datetime, time, timedelta

from odoo import _, fields
from odoo.tests import tagged

from .common import SFACommon


@tagged("post_install", "-at_install", "sales_field_sfa")
class TestDashboard(SFACommon):

    def test_dashboard_shape(self):
        """get_dashboard_data devuelve las claves esperadas con tipos correctos."""
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-01"
        )
        expected_keys = {
            "period", "period_suffix",
            "month_start", "month_end", "is_manager", "selected_user",
            "user_options", "labels", "kpis", "lists", "actions",
            "currency", "manager", "has_account",
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertFalse(data["is_manager"])
        self.assertFalse(data["manager"]["enabled"])

    def test_dashboard_labels_populated(self):
        """labels expone los strings humanos de interaction_type y result.

        Comparamos contra la propia selección del modelo (no contra un literal
        en español) para que el test sea agnóstico del idioma de la base."""
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-01"
        )
        self.assertIn("interaction_type", data["labels"])
        self.assertIn("result", data["labels"])
        model_types = dict(self.Interaction._fields["interaction_type"]._description_selection(self.env))
        model_results = dict(self.Interaction._fields["result"]._description_selection(self.env))
        self.assertEqual(data["labels"]["interaction_type"]["visit"], model_types["visit"])
        self.assertEqual(data["labels"]["result"]["contacted"], model_results["contacted"])

    def test_dashboard_kpi_sum_matches_total(self):
        """visit + call + whatsapp + followup == total_interactions."""
        # Crea 3 interacciones para el vendedor en mayo 2026 sin tocar partner ajeno.
        self.partner_orphan.user_id = self.seller_a
        for itype in ("visit", "visit", "call"):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": self.partner_orphan.id,
                "interaction_type": itype,
                "interaction_datetime": "2026-05-15 10:00:00",
                "result": "order_taken",
            })
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-15"
        )
        k = data["kpis"]
        self.assertEqual(k["total_interactions"], 3)
        self.assertEqual(k["visit"], 2)
        self.assertEqual(k["call"], 1)
        self.assertEqual(k["visit"] + k["call"] + k["whatsapp"] + k["followup"], k["total_interactions"])

    def test_manager_sees_team_summary(self):
        """Manager view incluye sellers_summary con vendedores en su grupo."""
        data = self.env["sales.field.dashboard"].with_user(self.manager).get_dashboard_data(
            date_ref="2026-05-01"
        )
        self.assertTrue(data["is_manager"])
        self.assertTrue(data["manager"]["enabled"])
        seller_ids = {row["seller_id"] for row in data["manager"]["sellers_summary"]}
        self.assertIn(self.seller_a.id, seller_ids)
        self.assertIn(self.seller_b.id, seller_ids)

    def test_dashboard_lists_due_today_and_week(self):
        """S-03: el dashboard expone due_today y due_this_week con la ultima interaccion
        de cada cliente que tenga next_action_date dentro del rango."""
        self.partner_orphan.user_id = self.seller_a
        today = fields.Date.context_today(self.env["sales.field.dashboard"])
        in_3_days = today + timedelta(days=3)
        # Crear interaccion con seguimiento programado en 3 dias
        self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "interaction_datetime": datetime.combine(today, time(10, 0)),
            "result": "interested",
            "next_action_date": in_3_days,
        })
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref=today.isoformat()
        )
        self.assertIn("due_today", data["lists"])
        self.assertIn("due_this_week", data["lists"])
        due_week_ids = {item["id"] for item in data["lists"]["due_this_week"]}
        # La interaccion debe aparecer en la semana
        all_for_partner = self.Interaction.search([
            ("user_id", "=", self.seller_a.id),
            ("partner_id", "=", self.partner_orphan.id),
        ])
        self.assertTrue(any(i.id in due_week_ids for i in all_for_partner),
                        "La interaccion con next_action_date en 3 dias debe aparecer en due_this_week.")

    def test_dashboard_overdue_excludes_partner_with_recent_followup(self):
        """S-02: una interaccion con next_action_date pasado QUEDA SALDADA si existe
        una interaccion posterior del mismo cliente. No debe aparecer como atrasada."""
        self.partner_orphan.user_id = self.seller_a
        today = fields.Date.context_today(self.env["sales.field.dashboard"])
        # Interaccion vieja con next_action_date ya vencido
        old = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "call",
            "interaction_datetime": datetime.combine(today - timedelta(days=10), time(10, 0)),
            "result": "interested",
            "next_action_date": today - timedelta(days=5),
        })
        # Vendedor "le da seguimiento": registra nueva interaccion mas reciente
        recent = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "interaction_datetime": datetime.combine(today, time(10, 0)),
            "result": "order_taken",
        })
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref=today.isoformat()
        )
        overdue_ids = {item["id"] for item in data["lists"]["overdue"]}
        self.assertNotIn(old.id, overdue_ids,
                         "La interaccion antigua debe quedar saldada por la nueva.")

    def test_dashboard_overdue_includes_unfollowed(self):
        """S-02: si NO hay interaccion posterior del cliente, la antigua SI aparece atrasada."""
        self.partner_orphan.user_id = self.seller_a
        today = fields.Date.context_today(self.env["sales.field.dashboard"])
        old = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "call",
            "interaction_datetime": datetime.combine(today - timedelta(days=10), time(10, 0)),
            "result": "interested",
            "next_action_date": today - timedelta(days=5),
        })
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref=today.isoformat()
        )
        overdue_ids = {item["id"] for item in data["lists"]["overdue"]}
        self.assertIn(old.id, overdue_ids,
                      "Sin seguimiento posterior, la interaccion vencida debe aparecer atrasada.")

    def test_dashboard_period_year_uses_year_range(self):
        """period='year' devuelve rango 1-enero a 31-diciembre del año del date_ref."""
        Dashboard = self.env["sales.field.dashboard"]
        data = Dashboard.with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-15", period="year"
        )
        self.assertEqual(data["period"], "year")
        self.assertEqual(data["month_start"], "2026-01-01")
        self.assertEqual(data["month_end"], "2026-12-31")
        self.assertEqual(data["period_suffix"], _("del Año"))

    def test_dashboard_period_month_default(self):
        """Sin parametro o con period='month' devuelve el mes."""
        Dashboard = self.env["sales.field.dashboard"]
        data = Dashboard.with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-15"
        )
        self.assertEqual(data["period"], "month")
        self.assertEqual(data["month_start"], "2026-05-01")
        self.assertEqual(data["month_end"], "2026-05-31")
        self.assertEqual(data["period_suffix"], _("del Mes"))

    def test_dashboard_period_year_aggregates_more_than_month(self):
        """Crear interacciones en distintos meses; period='year' suma todas, period='month' solo del mes."""
        from datetime import datetime, time
        self.partner_orphan.user_id = self.seller_a
        # 2 interacciones en marzo, 3 en mayo
        for dt in ("2026-03-10 10:00:00", "2026-03-20 10:00:00"):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": self.partner_orphan.id,
                "interaction_type": "visit",
                "interaction_datetime": dt,
                "result": "order_taken",
            })
        for dt in ("2026-05-05 10:00:00", "2026-05-15 10:00:00", "2026-05-25 10:00:00"):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": self.partner_orphan.id,
                "interaction_type": "call",
                "interaction_datetime": dt,
                "result": "order_taken",
            })
        Dashboard = self.env["sales.field.dashboard"]
        data_month = Dashboard.with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-15", period="month"
        )
        data_year = Dashboard.with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-15", period="year"
        )
        # Mes mayo: 3 interacciones; Año 2026: 5 (2 marzo + 3 mayo)
        self.assertEqual(data_month["kpis"]["total_interactions"], 3)
        self.assertEqual(data_year["kpis"]["total_interactions"], 5)

    def test_quotations_month_excludes_excluded_partner_quotes(self):
        """Cotizaciones de clientes excluidos NO cuentan en quotations_month."""
        self.partner_orphan.user_id = self.seller_a
        # Crear 2 cotizaciones del seller_a para el partner_orphan, en el mes actual
        SaleOrder = self.env["sale.order"]
        SaleOrder.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "user_id": self.seller_a.id,
        })
        SaleOrder.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "user_id": self.seller_a.id,
        })
        # Antes de excluir: el KPI cuenta esas 2 (mas las que ya pudieran existir)
        data_before = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        count_before = data_before["kpis"]["quotations_month"]
        # Gerencia excluye al partner
        self.partner_orphan.sudo().write({
            "sfa_excluded": True,
            "sfa_exclusion_reason": self.env.ref("sales_field_sfa.exclusion_reason_otro").id,
        })
        data_after = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        count_after = data_after["kpis"]["quotations_month"]
        # Despues debe ser menor (las 2 cotizaciones del excluido salen)
        self.assertLess(count_after, count_before,
                        "Las cotizaciones del partner excluido deben dejar de contar.")
        self.assertEqual(count_before - count_after, 2,
                         "Exactamente 2 cotizaciones del excluido deben salir.")

    def test_inactive_list_measures_only_owner_interactions(self):
        """#8 (2026-06-09): la inactividad se mide por el vendedor DUEÑO. Un cliente
        de seller_a contactado SOLO por seller_b sigue apareciendo como 'sin contacto'
        para seller_a. Se prueba via gerente (ve todas las interacciones por record
        rule) — es el caso donde el filtro user_id importa."""
        self.partner_orphan.user_id = self.seller_a
        # seller_b registra una interaccion RECIENTE sobre el cliente de seller_a.
        self.Interaction.with_user(self.seller_b).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        data = self.env["sales.field.dashboard"].with_user(self.manager).get_dashboard_data(
            target_user_id=self.seller_a.id
        )
        inactive_ids = {p["id"] for p in data["lists"]["inactive_partners"]}
        self.assertIn(
            self.partner_orphan.id, inactive_ids,
            "El cliente sin contacto propio debe aparecer inactivo aunque otro vendedor lo haya visto.",
        )

    def test_action_register_next_interaction_returns_form_with_defaults(self):
        """S-01: el action devuelve form con default_partner_id y default_user_id precargados."""
        self.partner_orphan.user_id = self.seller_a
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        action = interaction.with_user(self.seller_a).action_register_next_interaction()
        self.assertEqual(action["res_model"], "sales.interaction")
        self.assertEqual(action["view_mode"], "form")
        ctx = action.get("context") or {}
        self.assertEqual(ctx.get("default_partner_id"), self.partner_orphan.id)
        self.assertEqual(ctx.get("default_user_id"), self.seller_a.id)
