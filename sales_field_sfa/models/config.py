"""Ajustes del Seguimiento Comercial, integrados en Ajustes de Odoo.

Se usa res.config.settings (el panel nativo de Ajustes) para que la página tenga
la apariencia estándar de Odoo (barra lateral de apps + barra Guardar). Es, por
diseño de Odoo, un área de administración (grupo Settings); el menú de acceso se
restringe en consecuencia.

La fuente de verdad son los parámetros de ir.config_parameter (lo que lee el
dashboard); los campos `config_parameter=...` los sincroniza el framework.
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
        "CRM. Se aplica al instalar/actualizar el módulo o al guardar estos ajustes.",
    )

    def set_values(self):
        super().set_values()
        # Reaplica la visibilidad del menú CRM al guardar, sin esperar a un -u.
        self.env["res.config.settings"]._sfa_apply_crm_visibility()

    @api.model
    def _sfa_apply_crm_visibility(self):
        """Aplica (o revierte) el ocultamiento del menú CRM para los Usuarios de
        Seguimiento Comercial según el parámetro sales_field_sfa.hide_crm_for_users.

        Apunta al menú raíz de CRM por su xml_id estable `crm.crm_menu_root` y sus
        descendientes — agnóstico del idioma. Si CRM no está instalado, no hace nada."""
        group = self.env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
        if not group:
            return
        crm_root = self.env.ref("crm.crm_menu_root", raise_if_not_found=False)
        if not crm_root:
            return
        crm_menus = crm_root + self.env["ir.ui.menu"].search([("id", "child_of", crm_root.id)])
        hide = str(
            self.env["ir.config_parameter"].sudo().get_param("sales_field_sfa.hide_crm_for_users", "True")
        ).lower() not in ("false", "0", "")
        if hide:
            crm_menus.sudo().write({"groups_id": [(3, group.id)]})
            _logger.info("sales_field_sfa: menú CRM oculto para %s", group.name)
        else:
            crm_menus.sudo().write({"groups_id": [(4, group.id)]})
            _logger.info("sales_field_sfa: menú CRM visible para %s", group.name)
