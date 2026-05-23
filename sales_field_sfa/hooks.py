"""Hooks de instalacion/desinstalacion para sales_field_sfa.

post_init_hook: oculta los menus de CRM a los Usuarios de Seguimiento Comercial.
    Motivacion: vendedores de campo trabajan desde "Seguimiento Comercial" y no
    deben ver el modulo CRM (que es para un equipo distinto). Sin este hook, al
    instalar SFA con CRM ya instalado los vendedores SFA verian ambos menus.

    Limitaciones conocidas:
    - Si CRM se INSTALA DESPUES de SFA, los menus CRM nuevos no quedan ocultos
      hasta el siguiente -u sales_field_sfa.

uninstall_hook: revierte la accion del post_init_hook devolviendo el acceso a
    los menus CRM. Defensivo: si el grupo group_sales_field_user fue absorbido
    por otro modulo o sobrevive a la desinstalacion, no queremos dejar los
    menus CRM rotos por la huella historica de SFA.
"""


def post_init_hook(env):
    """Hide CRM root/menu entries for field users when CRM is installed."""
    group = env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
    if not group:
        return

    crm_menus = env["ir.ui.menu"].search([("name", "ilike", "CRM")])
    if crm_menus:
        crm_menus.write({"groups_id": [(3, group.id)]})


def uninstall_hook(env):
    """Restore CRM menu access for the former SFA user group, if it survives."""
    group = env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
    if not group:
        return

    crm_menus = env["ir.ui.menu"].search([("name", "ilike", "CRM")])
    if crm_menus:
        crm_menus.write({"groups_id": [(4, group.id)]})
