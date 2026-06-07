from . import models
from .hooks import post_init_hook, uninstall_hook

# Nota: NO importamos `tests` aquí. Odoo autodescubre el subpaquete `tests` en
# modo test (--test-enable); importarlo en __init__ lo carga en cada arranque y
# Odoo lo registra como ERROR ("Importing test framework... when not running in
# test mode"). Dejarlo fuera mantiene el log de arranque limpio.
