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
        """Asignar un estado de cliente desde catalogo funciona y se persiste."""
        prospect = self.env.ref("sales_field_sfa.customer_status_prospect")
        p = self.Partner.create({
            "name": "Prospecto SFA",
            "customer_rank": 1,
            "x_customer_status": prospect.id,
        })
        self.assertEqual(p.x_customer_status, prospect)
        self.assertEqual(p.x_customer_status.code, "prospect")

    def test_reject_notifies_requester(self):
        """W-01: al rechazar, el mensaje del chatter incluye al solicitante como partner notificado."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        interaction.with_user(self.manager).action_reject_assignment()
        # buscamos el mensaje mas reciente del chatter de la interaccion
        msgs = self.env["mail.message"].search([
            ("model", "=", "sales.interaction"),
            ("res_id", "=", interaction.id),
        ], order="id desc", limit=5)
        self.assertTrue(msgs, "Se esperaba al menos un mensaje en el chatter.")
        # alguno de los mensajes debe tener al solicitante como partner notificado
        seller_a_partner = self.seller_a.partner_id
        notified_anywhere = any(seller_a_partner in m.partner_ids for m in msgs)
        self.assertTrue(notified_anywhere, "El solicitante debe ser notificado en el chatter al rechazar.")

    def test_approve_notifies_requester(self):
        """W-01: al aprobar, el solicitante recibe notificacion dirigida en su interaccion."""
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        interaction.with_user(self.manager).action_approve_assignment()
        msgs = self.env["mail.message"].search([
            ("model", "=", "sales.interaction"),
            ("res_id", "=", interaction.id),
        ], order="id desc", limit=10)
        seller_a_partner = self.seller_a.partner_id
        self.assertTrue(any(seller_a_partner in m.partner_ids for m in msgs),
                        "El solicitante debe ser notificado al aprobar.")

    def test_partner_recent_interaction_count_excludes_current(self):
        """W-02: el compute cuenta interacciones recientes del partner sin contar la actual."""
        # Crear varias interacciones para el mismo partner
        first = self.Interaction.with_user(self.seller_b).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "call",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        second = self.Interaction.with_user(self.seller_b).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "whatsapp",
            "result": "interested",
            "next_action_date": "2026-12-31",
        })
        third = self.Interaction.with_user(self.seller_b).create({
            "partner_id": self.partner_owned_by_b.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        # Desde "third" deben verse las otras 2 (no a si misma)
        third.invalidate_recordset(["partner_recent_interaction_count"])
        self.assertEqual(third.partner_recent_interaction_count, 2)
        # action_view_partner_recent_interactions devuelve action con domain a las 5 mas recientes
        action = third.action_view_partner_recent_interactions()
        self.assertEqual(action["res_model"], "sales.interaction")
        # debe incluir first y second
        domain_ids = action["domain"][0][2]
        self.assertIn(first.id, domain_ids)
        self.assertIn(second.id, domain_ids)
        self.assertNotIn(third.id, domain_ids)

    def test_excluded_partner_blocks_interaction_create(self):
        """Cliente marcado x_sfa_excluded no permite crear nuevas interacciones."""
        self.partner_orphan.user_id = self.seller_a
        self.partner_orphan.sudo().write({
            "x_sfa_excluded": True,
            "x_sfa_exclusion_reason": self.env.ref("sales_field_sfa.exclusion_reason_mercado_libre").id,
        })
        with self.assertRaises(ValidationError):
            self.Interaction.with_user(self.seller_a).create({
                "partner_id": self.partner_orphan.id,
                "interaction_type": "visit",
                "result": "order_taken",
            })

    def test_excluded_partner_allows_writes_to_historical_interactions(self):
        """Las interacciones historicas no se rompen si despues se excluye al cliente."""
        # Crear interaccion ANTES de excluir
        self.partner_orphan.user_id = self.seller_a
        interaction = self.Interaction.with_user(self.seller_a).create({
            "partner_id": self.partner_orphan.id,
            "interaction_type": "visit",
            "result": "order_taken",
        })
        # Gerencia excluye al cliente despues
        self.partner_orphan.sudo().write({
            "x_sfa_excluded": True,
            "x_sfa_exclusion_reason": self.env.ref("sales_field_sfa.exclusion_reason_empresa_interna").id,
        })
        # Cargar la interaccion historica no debe fallar (no se re-evalua el constraint)
        # — el constraint es @api.constrains de partner_id, no se dispara en read
        loaded = self.Interaction.browse(interaction.id)
        self.assertEqual(loaded.partner_id, self.partner_orphan)

    def test_excluded_partner_not_in_inactive_dashboard_list(self):
        """Un partner excluido NO debe aparecer en 'Sin contacto 30 dias'."""
        self.partner_orphan.user_id = self.seller_a
        # Sin interacciones recientes — el partner calificaria normalmente como inactive
        self.partner_orphan.sudo().write({
            "x_sfa_excluded": True,
            "x_sfa_exclusion_reason": self.env.ref("sales_field_sfa.exclusion_reason_mercado_libre").id,
        })
        data = self.env["sales.field.dashboard"].with_user(self.seller_a).get_dashboard_data()
        inactive_ids = {p["id"] for p in data["lists"]["inactive_partners"]}
        self.assertNotIn(self.partner_orphan.id, inactive_ids,
                         "Cliente excluido no debe aparecer en lista de inactivos.")

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
