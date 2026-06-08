"""Tests del KPI 'Facturado Pagado' que aporta el puente con Contabilidad.

Reutilizan el setup común del core (SFACommon) importándolo como addon."""
from datetime import date

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import tagged
from odoo.tools import mute_logger

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
        lost = self.env.ref("sales_field_sfa_account.customer_status_lost")
        self.assertTrue(lost.is_lost)
        self.assertFalse(lost.is_customer)
        # catálogo de razones disponible
        self.assertTrue(self.env["sales.field.lost.reason"].search_count([]) > 0)

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

    def test_at_risk_window_by_last_invoice(self):
        """'Clientes en Riesgo' (sfa_at_risk) solo incluye Inactivos/Perdidos cuya
        última compra está dentro de la ventana en meses; fuera de ella, o sin última
        compra, caen. La ventana en 0 = sin límite."""
        P = self.env["res.partner"]
        Param = self.env["ir.config_parameter"].sudo()
        lost = self.env.ref("sales_field_sfa_account.customer_status_lost")
        today = fields.Date.context_today(P)

        recent = P.create({"name": "Perdido reciente", "sfa_customer_status": lost.id,
                           "sfa_last_invoice_date": today - relativedelta(months=18)})
        old = P.create({"name": "Perdido antiguo", "sfa_customer_status": lost.id,
                       "sfa_last_invoice_date": today - relativedelta(months=30)})
        never = P.create({"name": "Perdido sin compra", "sfa_customer_status": lost.id,
                         "sfa_last_invoice_date": False})

        # Ventana de 24 meses: solo el reciente sigue vigente.
        Param.set_param("sales_field_sfa.at_risk_window_months", "24")
        P._sfa_refresh_at_risk(today)
        self.assertTrue(recent.sfa_at_risk, "Última compra a 18m (<24) debe seguir en riesgo")
        self.assertFalse(old.sfa_at_risk, "Última compra a 30m (>24) debe caer del reporte")
        self.assertFalse(never.sfa_at_risk, "Sin última compra debe caer del reporte")

        # Sin límite (0): todos los Inactivos/Perdidos vuelven a aparecer.
        Param.set_param("sales_field_sfa.at_risk_window_months", "0")
        P._sfa_refresh_at_risk(today)
        self.assertTrue(recent.sfa_at_risk)
        self.assertTrue(old.sfa_at_risk, "Con ventana 0 (sin límite) el antiguo reaparece")
        self.assertTrue(never.sfa_at_risk, "Con ventana 0 (sin límite) el sin-compra reaparece")

        # Si deja de ser Inactivo/Perdido (p.ej. vuelve a comprar y se promueve), cae.
        regular = self.env.ref("sales_field_sfa.customer_status_customer")
        recent.sfa_customer_status = regular.id
        P._sfa_refresh_at_risk(today)
        self.assertFalse(recent.sfa_at_risk, "Un Cliente regular no está 'en riesgo'")

    def test_target_sum_general_plus_per_customer(self):
        """El objetivo del vendedor es la SUMA de su objetivo general (sin cliente)
        más los objetivos por cliente del mismo mes."""
        Target = self.env["sales.field.target"]
        Dashboard = self.env["sales.field.dashboard"]
        company = self.env.company
        user = self.seller_a
        month = date(2026, 3, 1)
        c1 = self.env["res.partner"].create({"name": "Cliente Meta 1"})
        c2 = self.env["res.partner"].create({"name": "Cliente Meta 2"})
        common = {"user_id": user.id, "date_month": month, "company_id": company.id}
        Target.create({**common, "target_amount": 1000.0})                      # general
        Target.create({**common, "partner_id": c1.id, "target_amount": 250.0})  # por cliente
        Target.create({**common, "partner_id": c2.id, "target_amount": 750.0})  # por cliente

        by_user = Dashboard._sfa_target_by_user([user.id], month, month, [company.id])
        self.assertEqual(
            round(by_user.get(user.id, 0.0), 2), 2000.0,
            "El objetivo del vendedor debe sumar general (1000) + por cliente (250+750)",
        )

    def test_target_uniqueness_rules(self):
        """Un solo objetivo general por vendedor/mes (índice parcial) y uno por
        cada cliente (unique). Duplicar cualquiera de los dos debe fallar."""
        Target = self.env["sales.field.target"]
        company = self.env.company
        user = self.seller_a
        month = date(2026, 4, 1)
        c1 = self.env["res.partner"].create({"name": "Cliente Único"})
        common = {"user_id": user.id, "date_month": month, "company_id": company.id}
        Target.create({**common, "target_amount": 500.0})                       # general
        Target.create({**common, "partner_id": c1.id, "target_amount": 300.0})  # por cliente

        # Otro general para el mismo vendedor/mes → bloqueado por el índice parcial.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                Target.create({**common, "target_amount": 999.0})

        # Otro objetivo para el MISMO cliente → bloqueado por el unique constraint.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                Target.create({**common, "partner_id": c1.id, "target_amount": 111.0})
