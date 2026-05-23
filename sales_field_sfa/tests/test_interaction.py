from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SFACommon


@tagged("post_install", "-at_install", "sales_field_sfa")
class TestInteractionCreate(SFACommon):

    def test_create_assigns_orphan_partner(self):
        """Partner sin user_id queda asignado al vendedor que crea la interaccion."""
        self.assertFalse(self.partner_orphan.user_id)
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        self.partner_orphan.invalidate_recordset(["user_id"])
        self.assertEqual(self.partner_orphan.user_id, self.seller_a)
        self.assertEqual(interaction.assignment_request_state, "not_requested")

    def test_create_requests_reassignment_when_partner_has_other_owner(self):
        """Interaccion sobre cliente ajeno crea solicitud + activities a managers."""
        Activity = self.env["mail.activity"]
        before = Activity.search_count([
            ("res_model", "=", "res.partner"),
            ("res_id", "=", self.partner_owned_by_b.id),
        ])
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        self.assertEqual(interaction.assignment_request_state, "requested")
        # why: el partner sigue siendo del vendedor original; solo se solicita.
        self.partner_owned_by_b.invalidate_recordset(["user_id"])
        self.assertEqual(self.partner_owned_by_b.user_id, self.seller_b)
        after = Activity.search_count([
            ("res_model", "=", "res.partner"),
            ("res_id", "=", self.partner_owned_by_b.id),
        ])
        self.assertGreater(after, before, "Se esperaba al menos una activity creada al gerente.")

    def test_next_action_date_required_for_open_results(self):
        """next_action_date obligatoria salvo en not_interested / order_taken."""
        with self.assertRaises(ValidationError):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": self.partner_orphan.id,
                "interaction_type": "visit",
                "result": "interested",
                # next_action_date intencionalmente ausente
            })

    def test_next_action_date_exempt_for_terminal_results(self):
        """order_taken y not_interested no requieren next_action_date."""
        rec = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "not_interested",
        })
        self.assertTrue(rec.id)

    def test_action_create_quotation_idempotent(self):
        """Llamar dos veces a action_create_quotation no crea dos sale.order."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        interaction.with_user(self.seller_a).action_create_quotation()
        first_order = interaction.sale_order_id
        self.assertTrue(first_order)
        interaction.with_user(self.seller_a).action_create_quotation()
        self.assertEqual(interaction.sale_order_id, first_order)
        self.assertEqual(first_order.origin, interaction.name)

    def test_interaction_name_uses_sequence(self):
        """El name se asigna desde la sequence con prefijo INT/."""
        rec = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        self.assertTrue(rec.name.startswith("INT/"), f"Folio inesperado: {rec.name}")
