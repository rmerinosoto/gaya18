# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    # Modelos de la Lista de Materiales cuya LECTURA queremos reservar
    # exclusivamente a los grupos de Manufactura ("el bom prendido").
    _GAYA_BOM_MODELS = ("mrp.bom", "mrp.bom.line", "mrp.bom.byproduct")

    @api.model
    def _gaya_restrict_bom_read(self):
        """Quita perm_read sobre mrp.bom(.line/.byproduct) a TODO grupo que no
        sea Manufactura / Usuario o Manufactura / Administrador.

        Resultado: solo los usuarios que tienen activada la autorizacion de
        Manufactura en su ficha pueden abrir/leer una lista de materiales,
        sin importar a que otros grupos pertenezcan (Contabilidad, Ventas,
        Compras, Inventario o grupos personalizados).

        Se invoca via <function> en el XML, de modo que se ejecuta en cada
        instalacion y actualizacion del modulo. Es idempotente y vuelve a
        aplicarse tras un upgrade de los modulos puente (mrp_account,
        sale_mrp, purchase_mrp) que regeneran sus ACL.
        """
        keep = self.env.ref("mrp.group_mrp_user") | self.env.ref(
            "mrp.group_mrp_manager"
        )
        accesses = self.search(
            [
                ("model_id.model", "in", list(self._GAYA_BOM_MODELS)),
                ("perm_read", "=", True),
            ]
        )
        to_revoke = accesses.filtered(
            lambda a: not a.group_id or a.group_id not in keep
        )
        if not to_revoke:
            _logger.info("gaya_mrp_bom_restrict: no hay ACL de lectura por revocar.")
            return
        revoked_groups = sorted(
            {a.group_id.display_name if a.group_id else "SIN GRUPO (todos)" for a in to_revoke}
        )
        to_revoke.write({"perm_read": False})
        _logger.info(
            "gaya_mrp_bom_restrict: revocada lectura de BOM en %s ACL. "
            "Grupos afectados: %s",
            len(to_revoke),
            ", ".join(revoked_groups),
        )
