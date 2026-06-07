"""Hooks de instalacion/desinstalacion para sales_field_sfa.

post_init_hook: aplica la visibilidad del menu CRM para los Usuarios de
    Seguimiento Comercial segun el ajuste `sales_field_sfa.hide_crm_for_users`
    (por defecto True = ocultar). Motivacion: los vendedores de campo trabajan
    desde "Seguimiento Comercial" y normalmente no deben ver el modulo CRM.

    La logica vive en res.config.settings._sfa_apply_crm_visibility() para poder
    reaplicarse tambien al guardar los Ajustes, sin esperar a un -u. Apunta al
    menu raiz de CRM por xml_id estable (crm.crm_menu_root), no por nombre — mas
    robusto y agnostico del idioma que la version anterior.

    Limitaciones conocidas:
    - Si CRM se INSTALA DESPUES de SFA, los menus CRM no quedan ocultos hasta el
      siguiente -u sales_field_sfa o hasta guardar los Ajustes de Seguimiento.

uninstall_hook: revierte el ocultamiento devolviendo el acceso al menu CRM.
"""


def post_init_hook(env):
    env["res.config.settings"]._sfa_apply_crm_visibility()


def uninstall_hook(env):
    """Restaura el acceso al menu CRM para el grupo SFA, si sobrevive."""
    group = env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
    if not group:
        return
    crm_root = env.ref("crm.crm_menu_root", raise_if_not_found=False)
    if not crm_root:
        return
    crm_menus = crm_root + env["ir.ui.menu"].search([("id", "child_of", crm_root.id)])
    crm_menus.sudo().write({"groups_id": [(4, group.id)]})
