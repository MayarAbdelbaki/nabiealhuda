# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        help="Address picked with the POS 'Delivery' button. The delivery "
             "stock.picking is routed here instead of the customer's own "
             "address when set.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        if not fields_list:
            return fields_list
        return fields_list + ['partner_shipping_id']

    def _create_order_picking(self):

        self.ensure_one()
        if self.shipping_date:
            return super()._create_order_picking()
        if not self._should_create_picking_real_time():
            return

        delivery_partner = self.partner_shipping_id or self.partner_id
        picking_type = self.config_id.picking_type_id
        if delivery_partner.property_stock_customer:
            destination_id = delivery_partner.property_stock_customer.id
        elif not picking_type or not picking_type.default_location_dest_id:
            destination_id = self.env['stock.warehouse']._get_partner_locations()[0].id
        else:
            destination_id = picking_type.default_location_dest_id.id

        pickings = self.env['stock.picking']._create_picking_from_pos_order_lines(
            destination_id, self.lines, picking_type, delivery_partner
        )
        pickings.write({
            'pos_session_id': self.session_id.id,
            'pos_order_id': self.id,
            'origin': self.name,
        })
