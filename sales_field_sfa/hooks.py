def post_init_hook(env):
    """Hide CRM root/menu entries for field users when CRM is installed."""
    group = env.ref("sales_field_sfa.group_sales_field_user", raise_if_not_found=False)
    if not group:
        return

    crm_menus = env["ir.ui.menu"].search([
        ("name", "ilike", "CRM"),
    ])
    if crm_menus:
        crm_menus.write({"groups_id": [(3, group.id)]})
