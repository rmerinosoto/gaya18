{
    "name": "Sales Field SFA - Contabilidad",
    "summary": "KPI 'Facturado Pagado' para el Seguimiento Comercial (puente con Contabilidad)",
    "version": "18.0.2.3.1",
    "category": "Sales",
    "author": "ANFEPI - Rodrigo Merino",
    "license": "LGPL-3",
    # Modulo puente: conecta el core sales_field_sfa (sin contabilidad) con account.
    # Aporta el KPI "Facturado Pagado del Mes/Año" reconstruyendo la fecha real de
    # pago por conciliación. Si no se instala, el dashboard funciona igual pero sin
    # las tarjetas de facturación.
    "depends": [
        "sales_field_sfa",
        "account",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/lifecycle_data.xml",
        "views/res_config_settings_views.xml",
        "views/target_views.xml",
        "views/lifecycle_views.xml",
        "views/report_views.xml",
    ],
    # auto_install: en cuanto la base tenga sales_field_sfa + account instalados,
    # este puente se instala solo (Gaya mantiene el KPI sin intervención manual).
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": True,
}
