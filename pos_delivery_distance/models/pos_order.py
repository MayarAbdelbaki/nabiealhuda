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
        return fields_list + ['partner_shipping_id']

    def _create_order_picking(self):
        """Route the delivery picking to ``partner_shipping_id`` when set.

        Core's ``_create_order_picking`` (point_of_sale/models/pos_order.py)
        hard-codes ``self.partner_id`` as both the picking partner and the
        source for the destination location, with no seam to swap in a
        different address -- so the real-time branch is duplicated here with
        ``partner_shipping_id`` substituted in. The scheduled-delivery branch
        (``self.shipping_date`` set, which routes through a stock rule/MTO
        instead of a plain picking) is untouched and still goes through core;
        the POS 'Delivery' button in this module only targets the common
        immediate-picking case.
        """
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
