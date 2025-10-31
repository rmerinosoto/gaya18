# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class StockPicking(models.Model):
    """
    Inherited to connect the picking with WooCommerce.
    @author: Maulik Barad on Date 14-Nov-2019.
    Migrated by Maulik Barad on Date 07-Oct-2021.
    """
    _inherit = "stock.picking"

    updated_in_woo = fields.Boolean(default=False)
    is_woo_delivery_order = fields.Boolean("WooCommerce Delivery Order")
    woo_instance_id = fields.Many2one("woo.instance.ept", "Woo Instance")
    canceled_in_woo = fields.Boolean("Cancelled In woo", default=False)


    def woo_manually_update_shipment(self):
        """
        This is used to manually update order fulfillment to Woo Commerce store.
        @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 24th Nov 2023.
        """
        order_id = self.sale_id
        self.env['sale.order'].update_woo_order_status(self.woo_instance_id, sales_orders=order_id)
        return True
