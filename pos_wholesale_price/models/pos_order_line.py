# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_wholesale = fields.Boolean(
        string="Wholesale Price Applied", default=False, readonly=True,
        help="Whether the Wholesale Price was applied on this order line.")
    wholesale_price_unit = fields.Float(
        string="Wholesale Unit Price", digits=0, readonly=True,
        help="Wholesale unit price used on this line, kept for reference even if the "
             "price is later changed manually.")
    wholesale_tax_ids = fields.Many2many(
        'account.tax', 'pos_order_line_wholesale_tax_rel', 'line_id', 'tax_id',
        string="Wholesale Taxes Used", readonly=True,
        help="Wholesale taxes used on this order line, kept for reference.")

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        return fields_list + ['is_wholesale', 'wholesale_price_unit', 'wholesale_tax_ids']
