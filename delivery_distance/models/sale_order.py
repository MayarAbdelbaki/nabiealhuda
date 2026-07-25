# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_street = fields.Char(related='partner_shipping_id.street', string='Street')
    delivery_street2 = fields.Char(related='partner_shipping_id.street2', string='Street 2')
    delivery_city = fields.Char(related='partner_shipping_id.city', string='City')
    delivery_state_id = fields.Many2one(related='partner_shipping_id.state_id', string='State')
    delivery_zip = fields.Char(related='partner_shipping_id.zip', string='Zip')
    delivery_country_id = fields.Many2one(related='partner_shipping_id.country_id', string='Country')
    delivery_phone = fields.Char(related='partner_shipping_id.phone', string='Phone')
    delivery_email = fields.Char(related='partner_shipping_id.email', string='Email')
    delivery_national_address = fields.Char(
        related='partner_shipping_id.x_national_address', string='العنوان الوطني',
    )
    delivery_partner_latitude = fields.Float(
        related='partner_shipping_id.partner_latitude', string='Delivery Latitude', digits=(10, 7),
    )
    delivery_partner_longitude = fields.Float(
        related='partner_shipping_id.partner_longitude', string='Delivery Longitude', digits=(10, 7),
    )
    delivery_map_url = fields.Char(string='Map Link', compute='_compute_delivery_map_url')

    @api.depends('delivery_partner_latitude', 'delivery_partner_longitude')
    def _compute_delivery_map_url(self):
        for order in self:
            if order.delivery_partner_latitude and order.delivery_partner_longitude:
                order.delivery_map_url = 'https://www.google.com/maps?q=%s,%s' % (
                    order.delivery_partner_latitude, order.delivery_partner_longitude,
                )
            else:
                order.delivery_map_url = False

    def write(self, vals):
        res = super().write(vals)
        # Re-rate the distance carrier whenever the shipping address changes.
        if 'partner_shipping_id' in vals:
            self._distance_recompute_delivery()
        return res

    def _distance_recompute_delivery(self):
        """Recompute the delivery price for distance-based carriers.

        Odoo caches the shipping price on the delivery line and only refreshes
        it when the carrier is re-applied, so a plain address edit would keep a
        stale price. This re-runs the rate and updates the line in place.
        """
        # Guard against re-entrancy: ``set_delivery_line`` (and an on-the-fly
        # geo_localize) write back to records and would otherwise loop.
        if self.env.context.get('distance_recomputing'):
            return
        for order in self.with_context(distance_recomputing=True):
            carrier = order.carrier_id
            if order.state not in ('draft', 'sent'):
                continue
            if not carrier or carrier.delivery_type != 'distance_based':
                continue
            result = carrier.rate_shipment(order)
            if result.get('success'):
                order.set_delivery_line(carrier, result['price'])
                _logger.info(
                    "Distance delivery: re-rated order %s -> %s",
                    order.name, result['price'],
                )
            else:
                _logger.info(
                    "Distance delivery: re-rate failed for order %s (%s)",
                    order.name, result.get('error_message'),
                )
