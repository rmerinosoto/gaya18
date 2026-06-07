"""Asistente de Ajustes del Seguimiento Comercial.

Por qué NO usamos res.config.settings: ese modelo es de administración
(requiere base.group_system) y el panel de Ajustes de Odoo solo lo renderiza
para administradores. Aquí el caso de uso es que el GERENTE SFA — que no es
admin del sistema — ajuste sus parámetros. Por eso usamos un TransientModel
propio con un formulario normal y ACL para el grupo de Gerencia.

La fuente de verdad sigue siendo ir.config_parameter (lo que lee el dashboard);
este asistente solo lee/escribe esos parámetros.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


def _get_int_param(env, key, default):
    raw = env["ir.config_parameter"].sudo().get_param(key)
    try:
        value = int(raw)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


class SalesFieldConfig(models.TransientModel):
    _name = "sales.field.config"
    _description = "Ajustes de Seguimiento Comercial"

    sfa_inactivity_days = fields.Integer(
        string="Días para 'cliente sin contacto'",
        default=30,
        help="Un cliente asignado aparece en la lista 'Sin contacto' del dashboard "
        "cuando no tiene interacciones en este número de días.",
    )
    sfa_week_horizon_days = fields.Integer(
        string="Horizonte de 'pendientes esta semana' (días)",
        default=7,
        help="Rango hacia adelante para la lista 'Pendientes esta semana' del dashboard.",
    )
    sfa_recent_interaction_days = fields.Integer(
        string="Ventana de 'interacciones recientes' (días)",
        default=90,
        help="Ventana usada para contar las interacciones recientes de un cliente "
        "(contexto que ve Gerencia al evaluar una reasignación).",
    )
    sfa_hide_crm_for_users = fields.Boolean(
        string="Ocultar el menú CRM a los vendedores de campo",
        default=True,
        help="Si está activado, los Usuarios de Seguimiento Comercial no ven el menú "
        "CRM. Se aplica al guardar estos ajustes.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        icp = self.env["ir.config_parameter"].sudo()
        res.update(
            sfa_inactivity_days=_get_int_param(self.env, "sales_field_sfa.inactivity_days", 30),
            sfa_week_horizon_days=_get_int_param(self.env, "sales_field_sfa.week_horizon_days", 7),
            sfa_recent_interaction_days=_get_int_param(self.env, "sales_field_sfa.recent_interaction_days", 90),
            sfa_hide_crm_for_users=str(
                icp.get_param("sales_field_sfa.hide_crm_for_users", "True")
            ).lower() not in ("false", "0", ""),
        )
        return res

    def action_save(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("sales_field_sfa.inactivity_days", self.sfa_inactivity_days or 30)
        icp.set_param("sales_field_sfa.week_horizon_days", self.sfa_week_horizon_days or 7)
        icp.set_param("sales_field_sfa.recent_interaction_days", self.sfa_recent_interaction_days or 90)
        icp.set_param(
            "sales_field_sfa.hide_crm_for_users",
            "True" if self.sfa_hide_crm_for_users else "False",
        )
        # Seam: el módulo puente (account) guarda sus propios parámetros aquí.
        self._sfa_save_extra()
        # Reaplica la visibilidad del menú CRM sin esperar a un -u.
        self._sfa_apply_crm_visibility()
        return {"type": "ir.actions.act_window_close"}

    def _sfa_save_extra(self):
        """Seam para que módulos puente persistan parámetros adicionales."""
        return

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
