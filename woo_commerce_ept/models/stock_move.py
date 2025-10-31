# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
from odoo import models, fields

_logger = logging.getLogger("WooCommerce")


class StockMove(models.Model):
    """
    Inherited model for adding custom fields in picking while creating it.
    @author: Maulik Barad on Date 14-Nov-2019.
    Migrated by Maulik Barad on Date 07-Oct-2021.
    """
    _inherit = "stock.move"

    def _get_new_picking_values(self):
        """
        This method sets Woocommerce instance in picking.
        @author: Maulik Barad on Date 14-Nov-2019.
        Migrated by Maulik Barad on Date 07-Oct-2021.
        """
        res = super(StockMove, self)._get_new_picking_values()
        order_id = self.sale_line_id.order_id
        if order_id.woo_order_id:
            res.update({'woo_instance_id': order_id.woo_instance_id.id, 'is_woo_delivery_order': True})
        return res

    def _action_assign(self, force_qty=False):
        # We inherited the base method here to set the instance values in picking while the picking type is dropship.
        res = super(StockMove, self)._action_assign(force_qty=force_qty)
        picking_ids = self.mapped('picking_id')
        for picking in picking_ids:
            if not picking.woo_instance_id and picking.sale_id and picking.sale_id.woo_instance_id:
                picking.write({'woo_instance_id': picking.sale_id.woo_instance_id.id, 'is_woo_delivery_order': True})
        return res

    def woo_auto_process_stock_move_ept(self):
        """
        This method is use to check if stock move contain the lot/serial product but stock is not available then cron check
        if stock is received then it assigned and done the stock move.
        """
        move_ids = self.get_pending_stock_move_of_woo_orders()
        moves = self.browse(move_ids)
        for move in moves:
            try:
                move.picked = False
                move.move_line_ids.unlink()
                move._action_assign()
                move.picked = True
                move._action_done()
            except Exception as error:
                message = "Receive error while assign stock to stock move(%s) of shipped order, Error is:  (%s)" % (
                    move, error)
                _logger.info(message)
        return True

    def get_pending_stock_move_of_woo_orders(self):
        """
        This method is use to prepare a query to get stock move
        """
        sm_query = """
                    SELECT
                        sm.id as move_id,
                        so.id as so_id
                    FROM 
                        stock_move  as sm
                    INNER JOIN
                        sale_order_line as sol on sol.id = sm.sale_line_id 
                    INNER JOIN
                        sale_order as so on so.id = sol.order_id
                    INNER JOIN
                        product_product as pp on pp.id = sm.product_id
                    INNER JOIN
                        product_template as pt on pt.id = pp.product_tmpl_id
                    WHERE
                        picking_id is null AND
                        sale_line_id is not null AND
                        so.woo_order_id is not null AND
                        sm.state in ('confirmed','partially_available','assigned') AND
                        pt.tracking in ('lot','serial')                  
                    limit 100
                   """
        self._cr.execute(sm_query)
        result = self._cr.dictfetchall()
        move_ids = [data.get('move_id') for data in result]
        return move_ids
