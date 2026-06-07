"""Hook de instalación del puente.

Fija is_inactive=True en el estado 'Inactivo' del core en una INSTALACIÓN nueva
(donde las migraciones no corren). En upgrades lo hace la migración 18.0.2.1.0.
"""


def post_init_hook(env):
    inactive = env.ref("sales_field_sfa.customer_status_inactive", raise_if_not_found=False)
    if inactive and not inactive.is_inactive:
        inactive.is_inactive = True
