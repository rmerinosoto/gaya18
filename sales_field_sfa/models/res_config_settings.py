"""Ajustes configurables del Seguimiento Comercial.

Las ventanas temporales del dashboard y el comportamiento de ocultar CRM eran
constantes hardcodeadas. Aqui se exponen como `res.config.settings` respaldadas
por `ir.config_parameter`, para que cada empresa las ajuste sin tocar codigo.

El modulo puente sales_field_sfa_account agrega su propio parametro
(invoice_lookback_days) extendiendo este mismo modelo.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sfa_inactivity_days = fields.Integer(
        string="Días para 'cliente sin contacto'",
        config_parameter="sales_field_sfa.inactivity_days",
        default=30,
        help="Un cliente asignado aparece en la lista 'Sin contacto' del dashboard "
        "cuando no tiene interacciones en este número de días.",
    )
    sfa_week_horizon_days = fields.Integer(
        string="Horizonte de 'pendientes esta semana' (días)",
        config_parameter="sales_field_sfa.week_horizon_days",
        default=7,
        help="Rango hacia adelante para la lista 'Pendientes esta semana' del dashboard.",
    )
    sfa_recent_interaction_days = fields.Integer(
        string="Ventana de 'interacciones recientes' (días)",
        config_parameter="sales_field_sfa.recent_interaction_days",
        default=90,
        help="Ventana usada para contar las interacciones recientes de un cliente "
        "(contexto que ve Gerencia al evaluar una reasignación).",
    )
    sfa_hide_crm_for_users = fields.Boolean(
        string="Ocultar el menú CRM a los vendedores de campo",
        config_parameter="sales_field_sfa.hide_crm_for_users",
        default=True,
        help="Si está activado, los Usuarios de Seguimiento Comercial no ven el menú "
        "CRM (trabajan solo desde Seguimiento Comercial). Aplica al instalar/actualizar "
        "el módulo o al guardar estos ajustes.",
    )

    def set_values(self):
        super().set_values()
        # Re-aplica la visibilidad del menu CRM al guardar, sin esperar a un -u.
        self.env["res.config.settings"]._sfa_apply_crm_visibility()

    @api.model
    def _sfa_apply_crm_visibility(self):
        """Aplica (o revierte) el ocultamiento del menu CRM para los Usuarios de
        Seguimiento Comercial segun el parametro sales_field_sfa.hide_crm_for_users.

        Robustez vs la version vieja (que buscaba menus por name ilike 'CRM',
        fragil y dependiente del idioma): apuntamos al menu raiz de CRM por su
        xml_id estable `crm.crm_menu_root` y sus descendientes. Si CRM no esta
        instalado, no hace nada."""
        group = self.env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
        if not group:
            return
        crm_root = self.env.ref("crm.crm_menu_root", raise_if_not_found=False)
        if not crm_root:
            # CRM no instalado: nada que ocultar.
            return

        crm_menus = crm_root + self.env["ir.ui.menu"].search([("id", "child_of", crm_root.id)])
        hide = self.env["ir.config_parameter"].sudo().get_param(
            "sales_field_sfa.hide_crm_for_users", "True"
        )
        hide = str(hide).lower() not in ("false", "0", "")
        if hide:
            # (3, id) = quitar el grupo de groups_id → el menu deja de verse para
            # quien SOLO tenga ese grupo. Otros grupos del usuario lo siguen mostrando.
            crm_menus.sudo().write({"groups_id": [(3, group.id)]})
            _logger.info("sales_field_sfa: menu CRM oculto para %s", group.name)
        else:
            crm_menus.sudo().write({"groups_id": [(4, group.id)]})
            _logger.info("sales_field_sfa: menu CRM visible para %s", group.name)
