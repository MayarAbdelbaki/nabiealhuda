# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_sales_price = fields.Float(
        string="سعر البيع", related='product_id.lst_price', readonly=True,
        help="Saved sales price on the product, for reference only. Does not "
             "affect the actual unit price charged on this line.")
    product_cost_price = fields.Float(
        string="التكلفة", related='product_id.standard_price', readonly=True,
        help="Saved cost on the product, for reference only.")
