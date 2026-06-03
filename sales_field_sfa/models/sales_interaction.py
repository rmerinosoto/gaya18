from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SalesInteraction(models.Model):
    _name = "sales.interaction"
    _description = "Interacción Comercial"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "interaction_datetime desc, id desc"
    # why: enforça check_company=True en los Many2one declarados con ese flag.
    # Sin esto el flag se ignora silenciosamente.
    _check_company_auto = True

    name = fields.Char(
        string="Referencia",
        readonly=True,
        copy=False,
        default=lambda self: _("Nuevo"),
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        tracking=True,
        index=True,
        check_company=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    interaction_type = fields.Selection(
        [
            ("visit", "Visita"),
            ("call", "Llamada"),
            ("whatsapp", "WhatsApp"),
            ("followup", "Seguimiento"),
        ],
        string="¿Cómo lo contactaste?",
        required=True,
        tracking=True,
        help="Forma en que contactaste al cliente: visita en persona, llamada, mensaje de WhatsApp o seguimiento general.",
    )
    interaction_datetime = fields.Datetime(
        string="Fecha y Hora",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
        help="Cuándo ocurrió el contacto. Se llena con la fecha y hora actual por defecto.",
    )
    result = fields.Selection(
        [
            ("contacted", "Contactado"),
            ("no_answer", "No respondió"),
            ("not_available", "No disponible"),
            ("interested", "Interesado"),
            ("not_interested", "No interesado"),
            ("quotation_sent", "Cotización enviada"),
            ("order_taken", "Pedido tomado"),
        ],
        string="¿Cómo terminó?",
        required=True,
        tracking=True,
        help="Resultado del contacto. Si seleccionas Interesado, Cotización enviada o Pedido tomado, podrás generar una cotización.",
    )
    next_action_date = fields.Date(
        string="¿Cuándo vuelvo a contactar?",
        index=True,
        help="Fecha en la que volverás a buscar a este cliente. Obligatoria salvo que el resultado sea 'No interesado' o 'Pedido tomado'.",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotización",
        check_company=True,
        help="Cotización generada desde esta interacción. Se llena automáticamente al pulsar 'Crear Cotización'.",
    )
    notes = fields.Text(
        string="¿Qué pasó? (notas)",
        help="Detalles del contacto: lo que dijo el cliente, productos que pidió, observaciones que quieras recordar.",
    )
    partner_channel = fields.Many2one(
        "sales.field.channel",
        related="partner_id.x_channel",
        string="Canal",
        readonly=False,
        help="Canal comercial del cliente. Editar aquí actualiza la ficha del cliente.",
    )
    partner_visit_frequency = fields.Many2one(
        "sales.field.visit.frequency",
        related="partner_id.x_visit_frequency",
        string="Frecuencia de Visita",
        readonly=False,
        help="Cada cuánto se visita a este cliente. Editar aquí actualiza la ficha del cliente.",
    )
    assignment_request_state = fields.Selection(
        [
            ("not_requested", "Sin solicitud"),
            ("requested", "Esperando a Gerencia"),
            ("approved", "Aprobada"),
            ("rejected", "Rechazada"),
        ],
        string="Solicitud de Asignación",
        default="not_requested",
        readonly=True,
        tracking=True,
        copy=False,
        help="Estado de la solicitud cuando este cliente ya pertenece a otro vendedor y pides reasignarlo.",
    )
    assignment_request_date = fields.Datetime(
        string="Fecha Solicitud Asignación",
        readonly=True,
        copy=False,
    )
    assignment_requested_by_id = fields.Many2one(
        "res.users",
        string="Solicitada Por",
        readonly=True,
        copy=False,
    )
    # W-02: contexto visible para el gerente al evaluar una solicitud de reasignacion.
    # Cuenta de interacciones recientes del partner (excluye la actual). Compute
    # sin store, barato — solo se evalua al abrir el form.
    partner_recent_interaction_count = fields.Integer(
        string="Interacciones recientes del cliente",
        compute="_compute_partner_recent_interactions",
        help="Cantidad de interacciones registradas con este cliente en los últimos 90 días (excluyendo la actual).",
    )

    @api.depends("partner_id")
    def _compute_partner_recent_interactions(self):
        threshold = fields.Datetime.now() - timedelta(days=90)
        for rec in self:
            if not rec.partner_id:
                rec.partner_recent_interaction_count = 0
                continue
            rec.partner_recent_interaction_count = self.search_count([
                ("partner_id", "=", rec.partner_id.id),
                ("id", "!=", rec.id or 0),
                ("interaction_datetime", ">=", fields.Datetime.to_string(threshold)),
            ])

    def action_view_partner_recent_interactions(self):
        """W-02: abre las ultimas 5 interacciones del partner (excluyendo la actual),
        ordenadas por fecha desc. Util al gerente para decidir una reasignacion con contexto."""
        self.ensure_one()
        recent = self.search([
            ("partner_id", "=", self.partner_id.id),
            ("id", "!=", self.id),
        ], order="interaction_datetime desc", limit=5)
        return {
            "type": "ir.actions.act_window",
            "name": _("Últimas interacciones de %(partner)s") % {"partner": self.partner_id.display_name},
            "res_model": "sales.interaction",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "target": "current",
            "domain": [("id", "in", recent.ids)],
        }

    _sql_constraints = [
        (
            "sales_interaction_name_uniq",
            "unique(name, company_id)",
            "La referencia debe ser única por compañía.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nuevo"):
                vals["name"] = seq.next_by_code("sales.interaction") or _("Nuevo")
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("user_id", self.env.user.id)
        records = super().create(vals_list)
        records._process_partner_assignment()
        return records

    @api.constrains("result", "next_action_date")
    def _check_next_action_date_required(self):
        exempt_results = {"not_interested", "order_taken"}
        for rec in self:
            if rec.result and rec.result not in exempt_results and not rec.next_action_date:
                raise ValidationError(
                    _(
                        "La Próxima Acción es obligatoria cuando el resultado no es "
                        "'No interesado' o 'Pedido tomado'."
                    )
                )

    @api.constrains("partner_id")
    def _check_partner_not_excluded(self):
        """No permitir registrar interacciones a clientes que Gerencia marco
        como excluidos del seguimiento (Mercado Libre, empresas internas, etc).
        El control evita que el vendedor evada la regla por inercia."""
        for rec in self:
            if rec.partner_id and rec.partner_id.x_sfa_excluded:
                raise ValidationError(
                    _(
                        "El cliente '%(partner)s' está excluido del Seguimiento Comercial. "
                        "Si necesitas registrar una interacción, contacta a Gerencia para "
                        "que revise la exclusión."
                    ) % {"partner": rec.partner_id.display_name}
                )

    def action_register_next_interaction(self):
        """S-01: abre el form de una NUEVA interaccion con el mismo cliente y
        vendedor precargados. La cadena queda implicita (mismo partner_id, orden
        por fecha) — sin campo parent_interaction_id en el schema."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Siguiente interacción"),
            "res_model": "sales.interaction",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_create_quotation(self):
        self.ensure_one()
        order = self.sale_order_id
        if not order:
            order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner_id.id,
                    "user_id": self.user_id.id,
                    "company_id": self.company_id.id,
                    "origin": self.name,
                }
            )
            self.sale_order_id = order.id

        return {
            "type": "ir.actions.act_window",
            "name": _("Cotización"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": order.id,
            "target": "current",
        }

    def action_request_partner_assignment(self):
        self.ensure_one()
        if not self.partner_id.user_id:
            self.partner_id.sudo().write({"user_id": self.user_id.id})
            self.assignment_request_state = "not_requested"
            self.assignment_request_date = False
            self.assignment_requested_by_id = False
            self.message_post(
                body=_("El cliente no tenía vendedor y se asignó automáticamente a %(user)s.") % {"user": self.user_id.display_name},
                subtype_xmlid="mail.mt_note",
            )
            return True
        if self.partner_id.user_id == self.user_id:
            raise UserError(_("Este cliente ya está asignado a este vendedor."))
        self._create_assignment_request()
        return True

    def action_approve_assignment(self):
        """Manager-only: reasigna el partner al user solicitante y cierra todas
        las solicitudes pendientes para el mismo partner."""
        self.ensure_one()
        if not self.env.user.has_group("sales_field_sfa.group_sales_field_manager"):
            raise UserError(_("Solo Gerencia puede aprobar reasignaciones."))
        if self.assignment_request_state != "requested":
            raise UserError(_("Esta interacción no tiene una solicitud pendiente."))
        self.partner_id.sudo().write({"user_id": self.user_id.id})
        # why: una misma solicitud puede haber generado interacciones gemelas
        # (otro vendedor pidiendo lo mismo) — cerramos todas las pendientes del
        # partner para evitar que sigan apareciendo abiertas tras la decision.
        pending = self.search([
            ("partner_id", "=", self.partner_id.id),
            ("assignment_request_state", "=", "requested"),
        ])
        pending.write({"assignment_request_state": "approved"})
        self.partner_id.message_post(
            body=_("Reasignación aprobada por %(mgr)s. Nuevo vendedor: %(user)s.") % {
                "mgr": self.env.user.display_name,
                "user": self.user_id.display_name,
            },
            subtype_xmlid="mail.mt_note",
        )
        # W-01: notificar al solicitante en su propia interaccion con un mensaje dirigido.
        # message_post sobre cada interaction pendiente con partner_ids al solicitante
        # crea una notificacion explicita en su inbox/correo, no solo nota en chatter.
        for rec in pending:
            requester = rec.assignment_requested_by_id or rec.user_id
            if requester and requester.partner_id:
                rec.message_post(
                    body=_("Tu solicitud de reasignación fue %(decision)s por %(mgr)s. El cliente %(partner)s ahora es tuyo.") % {
                        "decision": _("aprobada"),
                        "mgr": self.env.user.display_name,
                        "partner": rec.partner_id.display_name,
                    },
                    partner_ids=[requester.partner_id.id],
                    subtype_xmlid="mail.mt_comment",
                )
        return True

    def action_reject_assignment(self):
        self.ensure_one()
        if not self.env.user.has_group("sales_field_sfa.group_sales_field_manager"):
            raise UserError(_("Solo Gerencia puede rechazar reasignaciones."))
        if self.assignment_request_state != "requested":
            raise UserError(_("Esta interacción no tiene una solicitud pendiente."))
        self.write({"assignment_request_state": "rejected"})
        # W-01: notificacion dirigida al solicitante (inbox/correo), no solo nota en chatter.
        requester = self.assignment_requested_by_id or self.user_id
        if requester and requester.partner_id:
            self.message_post(
                body=_("Tu solicitud de reasignación fue rechazada por %(mgr)s. El cliente %(partner)s sigue con su vendedor actual.") % {
                    "mgr": self.env.user.display_name,
                    "partner": self.partner_id.display_name,
                },
                partner_ids=[requester.partner_id.id],
                subtype_xmlid="mail.mt_comment",
            )
        else:
            self.message_post(
                body=_("Solicitud de reasignación rechazada por %(mgr)s.") % {"mgr": self.env.user.display_name},
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _process_partner_assignment(self):
        for rec in self:
            partner = rec.partner_id
            if not partner:
                continue
            # why: bloqueamos la fila del partner para evitar que dos vendedores
            # creando interacciones simultaneas del mismo cliente sin user_id
            # se pisen el ultimo write. SELECT FOR UPDATE re-lee el estado
            # actual y serializa con cualquier transaccion concurrente.
            # El flush previo asegura que escrituras pendientes en el ORM ya
            # esten en disco antes del SELECT raw — sin esto, dos transacciones
            # concurrentes podrian leer user_id=NULL y pisarse.
            self.env.flush_all()
            self.env.cr.execute(
                "SELECT user_id FROM res_partner WHERE id = %s FOR UPDATE",
                (partner.id,),
            )
            current_user_id = self.env.cr.fetchone()[0]
            partner.invalidate_recordset(["user_id"])

            if not current_user_id:
                partner.sudo().write({"user_id": rec.user_id.id})
                rec.write(
                    {
                        "assignment_request_state": "not_requested",
                        "assignment_request_date": False,
                        "assignment_requested_by_id": False,
                    }
                )
                rec.message_post(
                    body=_("Cliente asignado automáticamente a %(user)s por no tener vendedor previo.") % {"user": rec.user_id.display_name},
                    subtype_xmlid="mail.mt_note",
                )
            elif current_user_id != rec.user_id.id:
                rec._create_assignment_request()

    def _create_assignment_request(self):
        self.ensure_one()
        manager_group = self.env.ref("sales_field_sfa.group_sales_field_manager", raise_if_not_found=False)
        if not manager_group:
            return False

        managers = manager_group.users.filtered(lambda u: u.active and not u.share)
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = self.env["ir.model"]._get_id("res.partner")
        note = _(
            "El vendedor %(user)s solicita reasignación del cliente %(partner)s "
            "(actualmente asignado a %(current_owner)s) desde la interacción %(interaction)s."
        ) % {
            "user": self.user_id.display_name,
            "partner": self.partner_id.display_name,
            "current_owner": self.partner_id.user_id.display_name,
            "interaction": self.name,
        }

        if activity_type and managers:
            for manager in managers:
                self.env["mail.activity"].create(
                    {
                        "activity_type_id": activity_type.id,
                        "summary": _("Solicitud de reasignación de cliente"),
                        "note": note,
                        "res_model_id": model_id,
                        "res_id": self.partner_id.id,
                        "user_id": manager.id,
                        "date_deadline": fields.Date.context_today(self),
                    }
                )

        self.write(
            {
                "assignment_request_state": "requested",
                "assignment_request_date": fields.Datetime.now(),
                "assignment_requested_by_id": self.env.user.id,
            }
        )
        self.message_post(body=_("Solicitud de reasignación enviada a Gerencia."), subtype_xmlid="mail.mt_note")
        self.partner_id.message_post(body=note, subtype_xmlid="mail.mt_note")
        return True
