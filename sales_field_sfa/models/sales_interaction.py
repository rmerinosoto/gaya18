from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SalesInteraction(models.Model):
    _name = "sales.interaction"
    _description = "Interacción Comercial"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "interaction_datetime desc, id desc"

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
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
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
        string="Tipo de Interacción",
        required=True,
        tracking=True,
    )
    interaction_datetime = fields.Datetime(
        string="Fecha y Hora",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
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
        string="Resultado",
        required=True,
        tracking=True,
    )
    next_action_date = fields.Date(string="Próxima Acción")
    sale_order_id = fields.Many2one("sale.order", string="Cotización")
    notes = fields.Text(string="Notas")
    partner_channel = fields.Selection(
        related="partner_id.x_channel",
        string="Canal",
        readonly=False,
    )
    partner_visit_frequency = fields.Selection(
        related="partner_id.x_visit_frequency",
        string="Frecuencia de Visita",
        readonly=False,
    )
    assignment_request_state = fields.Selection(
        [
            ("not_requested", "No solicitada"),
            ("requested", "Solicitada"),
        ],
        string="Solicitud de Asignación",
        default="not_requested",
        readonly=True,
        tracking=True,
        copy=False,
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

    def _process_partner_assignment(self):
        for rec in self:
            partner = rec.partner_id
            if not partner:
                continue
            if not partner.user_id:
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
            elif partner.user_id != rec.user_id:
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
