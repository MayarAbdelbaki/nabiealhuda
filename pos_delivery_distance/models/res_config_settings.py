# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_delivery_carrier_id = fields.Many2one(
        related='pos_config_id.delivery_carrier_id', readonly=False,
    )
    pos_delivery_product_id = fields.Many2one(
        related='pos_config_id.delivery_product_id', readonly=False,
    )
