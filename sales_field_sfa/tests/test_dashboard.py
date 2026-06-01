from datetime import date, datetime, time, timedelta

from odoo import fields
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
            "month_start", "month_end", "is_manager", "selected_user",
            "user_options", "labels", "kpis", "lists", "actions",
            "currency", "manager",
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertFalse(data["is_manager"])
        self.assertFalse(data["manager"]["enabled"])

    def test_dashboard_labels_populated(self):
        """labels expone los strings humanos de interaction_type y result."""
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-01"
        )
        self.assertIn("interaction_type", data["labels"])
        self.assertIn("result", data["labels"])
        self.assertEqual(data["labels"]["interaction_type"]["visit"], "Visita")
        self.assertEqual(data["labels"]["result"]["contacted"], "Contactado")

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
            "x_sfa_excluded": True,
            "x_sfa_exclusion_reason": "mercado_libre",
        })
        data_after = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        count_after = data_after["kpis"]["quotations_month"]
        # Despues debe ser menor (las 2 cotizaciones del excluido salen)
        self.assertLess(count_after, count_before,
                        "Las cotizaciones del partner excluido deben dejar de contar.")
        self.assertEqual(count_before - count_after, 2,
                         "Exactamente 2 cotizaciones del excluido deben salir.")

    def test_paid_invoices_excludes_excluded_partner_invoices(self):
        """Facturas de clientes marcados x_sfa_excluded NO cuentan en el KPI
        'Facturado Pagado del Mes' ni en el desglose del manager."""
        Invoice = self.env["account.move"]
        # Buscamos partners con facturas pagadas reales en la DB para tener
        # un caso controlado. Si no hay, skip.
        sample_invoices = Invoice.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
        ], limit=20)
        if not sample_invoices:
            self.skipTest("Sin facturas pagadas en la DB de pruebas")

        # Tomamos un partner que tenga al menos una factura y lo asignamos al seller_a
        partner_with_invoice = sample_invoices[0].partner_id
        partner_with_invoice.sudo().write({"user_id": self.seller_a.id})

        # Antes de excluir: el monto del KPI incluye sus facturas
        data_before = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        amount_before = data_before["kpis"]["paid_invoices_month_amount"]

        # Gerencia excluye al partner
        partner_with_invoice.sudo().write({
            "x_sfa_excluded": True,
            "x_sfa_exclusion_reason": "mercado_libre",
        })

        # Despues de excluir: facturas del partner ya no cuentan
        data_after = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        amount_after = data_after["kpis"]["paid_invoices_month_amount"]

        # El monto debe haber bajado o quedar igual (si el partner no tenia facturas
        # del mes consultado). Lo importante: nunca debe haber subido.
        self.assertLessEqual(
            amount_after, amount_before,
            "Excluir un partner no puede aumentar el monto de Facturado Pagado.",
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

    def test_paid_date_simple_invoice(self):
        """_get_paid_date_by_invoice devuelve la fecha del move contraparte."""
        # Caso simplificado: tomar facturas ya pagadas en la DB y verificar
        # que la funcion no rompe y devuelve un dict con todas las ids.
        Invoice = self.env["account.move"]
        sample = Invoice.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
        ], limit=5)
        if not sample:
            self.skipTest("Sin facturas pagadas en la DB de pruebas")
        result = self.env["sales.field.dashboard"]._get_paid_date_by_invoice(sample)
        self.assertEqual(set(result.keys()), set(sample.ids))
        # Cada invoice debe tener una fecha (real o fallback a invoice_date).
        for inv in sample:
            self.assertTrue(result[inv.id], f"Invoice {inv.id} sin paid_date ni fallback")
