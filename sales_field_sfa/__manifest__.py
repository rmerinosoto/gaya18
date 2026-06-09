{
    "name": "Sales Field SFA",
    "summary": "Seguimiento comercial de campo con panel OWL",
    "version": "18.0.2.0.2",
    "category": "Sales",
    "author": "ANFEPI - Rodrigo Merino",
    "license": "LGPL-3",
    # El core NO depende de `account`: el KPI contable "Facturado Pagado" lo
    # aporta el modulo puente opcional `sales_field_sfa_account`. Asi una empresa
    # que solo quiera seguimiento de campo no arrastra toda la contabilidad.
    "depends": [
        "base",
        "mail",
        "contacts",
        "sale_management",
        "web",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/catalogs.xml",
        "views/catalog_views.xml",
        "views/partner_views.xml",
        "views/interaction_views.xml",
        "views/dashboard_action.xml",
        "views/menu.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [
        "demo/catalogs_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sales_field_sfa/static/src/js/dashboard.js",
            "sales_field_sfa/static/src/xml/dashboard.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "images": ["static/description/icon.png"],
    "application": True,
    "installable": True,
}
