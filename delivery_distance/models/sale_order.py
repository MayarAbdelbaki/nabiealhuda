# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
