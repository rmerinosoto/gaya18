# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ExampleModel(models.Model):
    """
    Example model demonstrating basic Odoo model structure.
    
    This model includes:
    - Basic field types
    - Computed fields
    - Constraints
    - Methods
    """
    _name = 'example.model'
    _description = 'Example Model'
    _order = 'name'
    _rec_name = 'name'

    # Basic Fields
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the example record'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, it will allow you to hide the record without removing it'
    )
    
    # Selection Field
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    
    # Numeric Fields
    quantity = fields.Integer(
        string='Quantity',
        default=0,
        help='Quantity value'
    )
    
    price = fields.Float(
        string='Price',
        digits=(12, 2),
        default=0.0,
        help='Price per unit'
    )
    
    # Date Fields
    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        help='Record date'
    )
    
    datetime = fields.Datetime(
        string='Date Time',
        default=fields.Datetime.now,
        help='Record date and time'
    )
    
    # Relational Field
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        help='User responsible for this record'
    )
    
    # Computed Field
    total = fields.Float(
        string='Total',
        compute='_compute_total',
        store=True,
        digits=(12, 2),
        help='Computed total: quantity * price'
    )
    
    # Constraints
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'The name must be unique!'),
        ('quantity_positive', 'CHECK(quantity >= 0)', 'Quantity must be positive!'),
    ]
    
    @api.depends('quantity', 'price')
    def _compute_total(self):
        """
        Compute total based on quantity and price.
        """
        for record in self:
            record.total = record.quantity * record.price
    
    @api.constrains('price')
    def _check_price(self):
        """
        Validate that price is not negative.
        """
        for record in self:
            if record.price < 0:
                raise ValidationError('Price cannot be negative!')
    
    def action_confirm(self):
        """
        Confirm the record.
        """
        self.ensure_one()
        self.state = 'confirmed'
        return True
    
    def action_done(self):
        """
        Mark the record as done.
        """
        self.ensure_one()
        self.state = 'done'
        return True
    
    def action_cancel(self):
        """
        Cancel the record.
        """
        self.ensure_one()
        self.state = 'cancelled'
        return True
    
    def action_draft(self):
        """
        Reset the record to draft.
        """
        self.ensure_one()
        self.state = 'draft'
        return True
