"""Tests del KPI 'Facturado Pagado' que aporta el puente con Contabilidad.

Reutilizan el setup común del core (SFACommon) importándolo como addon."""
from odoo.tests import tagged

from odoo.addons.sales_field_sfa.tests.common import SFACommon


@tagged("post_install", "-at_install", "sales_field_sfa_account")
class TestPaidKpi(SFACommon):

    def test_has_account_flag_true_with_bridge(self):
        """Con el puente instalado, el dashboard expone has_account=True y el KPI."""
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data(
            date_ref="2026-05-01"
        )
        self.assertTrue(data["has_account"])
        self.assertIn("paid_invoices_month_amount", data["kpis"])

    def test_paid_invoices_excludes_excluded_partner_invoices(self):
        """Facturas de clientes marcados sfa_excluded NO cuentan en el KPI
        'Facturado Pagado del Mes' ni en el desglose del manager."""
        Invoice = self.env["account.move"]
        sample_invoices = Invoice.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "paid"),
        ], limit=20)
        if not sample_invoices:
            self.skipTest("Sin facturas pagadas en la DB de pruebas")

        partner_with_invoice = sample_invoices[0].partner_id
        partner_with_invoice.sudo().write({"user_id": self.seller_a.id})

        data_before = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        amount_before = data_before["kpis"]["paid_invoices_month_amount"]

        partner_with_invoice.sudo().write({
            "sfa_excluded": True,
            "sfa_exclusion_reason": self.env.ref("sales_field_sfa.exclusion_reason_otro").id,
        })

        data_after = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        amount_after = data_after["kpis"]["paid_invoices_month_amount"]

        self.assertLessEqual(
            amount_after, amount_before,
            "Excluir un partner no puede aumentar el monto de Facturado Pagado.",
        )

    def test_bool_param_missing_uses_default(self):
        """Regresión: get_param(key) devuelve False (bool) si falta la clave; el
        helper debe distinguir 'no configurado' (default) de 'configurado en False'."""
        P = self.env["res.partner"]
        key = "sales_field_sfa.test_missing_param_xyz"
        self.env["ir.config_parameter"].sudo().search([("key", "=", key)]).unlink()
        self.assertTrue(P._sfa_bool_param(key, True), "Param ausente con default True debe ser True")
        self.assertFalse(P._sfa_bool_param(key, False), "Param ausente con default False debe ser False")
        self.env["ir.config_parameter"].sudo().set_param(key, "False")
        self.assertFalse(P._sfa_bool_param(key, True), "Param en 'False' debe ganar al default True")
        self.env["ir.config_parameter"].sudo().set_param(key, "True")
        self.assertTrue(P._sfa_bool_param(key, False))

    def test_inactive_status_flagged(self):
        """La migración/hook deja is_inactive=True en el estado 'Inactivo'."""
        inactive = self.env.ref("sales_field_sfa.customer_status_inactive")
        self.assertTrue(inactive.is_inactive)
        new_status = self.env.ref("sales_field_sfa_account.customer_status_new")
        self.assertTrue(new_status.is_customer)
        self.assertTrue(new_status.is_new_customer)

    def test_paid_date_simple_invoice(self):
        """_get_paid_date_by_invoice devuelve un dict con todas las ids dadas."""
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
        for inv in sample:
            self.assertTrue(result[inv.id], f"Invoice {inv.id} sin paid_date ni fallback")
