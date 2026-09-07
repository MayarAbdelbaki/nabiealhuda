# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    wholesale_price = fields.Float(
        string="سعر الجملة", digits='Product Price',
        help="Selling price used on a POS order line when Wholesale Price is applied. "
             "Does not affect the normal Sales Price.")
    wholesale_tax_ids = fields.Many2many(
        'account.tax', 'product_taxes_wholesale_rel', 'prod_id', 'tax_id',
        string="ضرائب مبيعات الجملة",
        domain=[('type_tax_use', '=', 'sale')],
        help="Taxes used on a POS order line when Wholesale Price is applied. "
             "Does not affect the normal Customer Taxes.")

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        return fields_list + ['wholesale_price', 'wholesale_tax_ids']
