# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Campos a auditar en el chatter de la PLANTILLA.
    # Para agregar otro campo: solo redefinelo aqui con tracking=True
    # (los demas atributos del core se conservan automaticamente).
    default_code = fields.Char(tracking=True)
