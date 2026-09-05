# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    delivery_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Delivery Method',
        help="Carrier used to price the delivery line added from the POS "
             "'Delivery' button -- any Delivery Method works, not just "
             "distance-based ones (see action_pos_rate_delivery on "
             "delivery.carrier for how each type is rated). Leave empty to "
             "hide that button for this point of sale.",
    )
    delivery_product_id = fields.Many2one(
        'product.product',
        string='Delivery Product',
        related='delivery_carrier_id.product_id',
        help="Product used for the delivery line added when a delivery "
             "address is picked in the POS. This is the Delivery Method's "
             "own product (every delivery.carrier already has one) -- it "
             "isn't set independently here, so it can't end up pointing at "
             "an unrelated product.",
    )

    def _get_special_products(self):
        # Force-load the delivery product into the POS session even though it
        # is not meant to appear in the regular product grid (same mechanism
        # pos_discount uses for its discount product): the 'Delivery' button
        # adds it to the order by code, so the client needs the record without
        # it being browsable/clickable in the catalog.
        res = super()._get_special_products()
        return res | self.env['pos.config'].search([]).mapped('delivery_product_id')
