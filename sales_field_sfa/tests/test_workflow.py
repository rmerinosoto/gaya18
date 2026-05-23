from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import SFACommon


@tagged("post_install", "-at_install", "sales_field_sfa")
class TestWorkflow(SFACommon):

    def test_check_company_blocks_cross_company_partner(self):
        """check_company=True bloquea partner de otra compania."""
        other_company = self.env["res.company"].create({"name": "Otra Compania SFA Test"})
        cross_partner = self.Partner.create({
            "name": "Cliente de otra compania",
            "company_id": other_company.id,
        })
        with self.assertRaises(UserError):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": cross_partner.id,
                "interaction_type": "visit",
                "result": "order_taken",
                # interaction usa env.company del seller_a (compania por defecto)
            })

    def test_check_company_allows_cross_company_partner_without_company(self):
        """Partners sin company_id (compartidos) siguen aceptados."""
        shared_partner = self.Partner.create({
            "name": "Cliente sin compania",
            "company_id": False,
        })
        rec = self.Interaction.with_user(self.seller_a).create({
            "partner_id": shared_partner.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        self.assertTrue(rec.id)

    def test_assignment_workflow_approve_reassigns_partner(self):
        """Manager aprueba: el partner pasa al vendedor solicitante."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        self.assertEqual(interaction.assignment_request_state, "requested")
        interaction.with_user(self.manager).action_approve_assignment()
        self.partner_owned_by_b.invalidate_recordset(["user_id"])
        self.assertEqual(self.partner_owned_by_b.user_id, self.seller_a)
        self.assertEqual(interaction.assignment_request_state, "approved")

    def test_assignment_workflow_reject_keeps_owner(self):
        """Manager rechaza: el partner sigue con su vendedor original."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        interaction.with_user(self.manager).action_reject_assignment()
        self.partner_owned_by_b.invalidate_recordset(["user_id"])
        self.assertEqual(self.partner_owned_by_b.user_id, self.seller_b)
        self.assertEqual(interaction.assignment_request_state, "rejected")

    def test_assignment_workflow_non_manager_cannot_approve(self):
        """Un vendedor que no es manager no puede aprobar."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        with self.assertRaises(UserError):
            interaction.with_user(self.seller_a).action_approve_assignment()

    def test_approve_closes_pending_for_same_partner(self):
        """Aprobar una solicitud cierra TODAS las pendientes del mismo partner."""
        i1 = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        # Otro vendedor solicita tambien (escenario raro pero posible)
        seller_c = self.User.create({
            "name": "Vendedor C SFA",
            "login": "sfa_test_seller_c",
            "email": "sfa_test_seller_c@example.test",
            "groups_id": [(6, 0, [self.group_user.id, self.group_sale_salesman.id])],
        })
        i2 = self.Interaction.with_user(seller_c).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "visit",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        self.assertEqual(i1.assignment_request_state, "requested")
        self.assertEqual(i2.assignment_request_state, "requested")
        i1.with_user(self.manager).action_approve_assignment()
        self.assertEqual(i1.assignment_request_state, "approved")
        i2.invalidate_recordset(["assignment_request_state"])
        self.assertEqual(i2.assignment_request_state, "approved")

    def test_partner_default_x_customer_status_is_empty(self):
        """Nuevos partners ya no quedan tagged como 'prospect' por default."""
        p = self.Partner.create({"name": "Partner sin status SFA"})
        self.assertFalse(p.x_customer_status)

    def test_partner_x_customer_status_still_writable(self):
        """Si el usuario marca explicitamente 'prospect', se persiste."""
        p = self.Partner.create({
            "name": "Prospecto SFA",
            "customer_rank": 1,
            "x_customer_status": "prospect",
        })
        self.assertEqual(p.x_customer_status, "prospect")

    def test_lock_serializes_concurrent_orphan_assignment(self):
        """SELECT FOR UPDATE evita que dos vendedores reasignen el mismo
        partner huerfano en paralelo con resultado inconsistente."""
        # En TransactionCase no podemos forzar concurrencia real, pero podemos
        # verificar que el flujo lee user_id POST-lock (la fuente de verdad).
        self.assertFalse(self.partner_orphan.user_id)
        self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        # Aqui ya esta asignado a seller_a. Un segundo create del seller_b debe
        # leer el estado POST-asignacion y solicitar reasignacion, no pisar.
        i2 = self.Interaction.with_user(self.seller_b).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        self.partner_orphan.invalidate_recordset(["user_id"])
        self.assertEqual(self.partner_orphan.user_id, self.seller_a)
        self.assertEqual(i2.assignment_request_state, "requested")
