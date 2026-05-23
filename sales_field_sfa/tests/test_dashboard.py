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
