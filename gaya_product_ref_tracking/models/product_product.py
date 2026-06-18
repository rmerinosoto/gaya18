# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Campos a auditar en el chatter de la VARIANTE.
    # Para agregar otro campo: solo redefinelo aqui con tracking=True
    # (los demas atributos del core se conservan automaticamente).
    default_code = fields.Char(tracking=True)
