# -*- coding: utf-8 -*-
from odoo import _, api, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    @api.model
    def action_pos_rate_delivery(self, carrier_id, partner_id, config_id):
        """RPC entry point for the POS 'Delivery' button.

        Thin wrapper around ``_distance_rate_for_partner`` (delivery_distance):
        there is no ``sale.order`` in the POS to call ``rate_shipment`` on, so
        the client talks to the shared distance-pricing engine directly. This
        keeps the POS and the website quoting the exact same price for the
        same address, since both end up calling the same method.

        The origin resolves the same way ``_distance_get_origin_partner`` does
        for a sale order (carrier override, then warehouse address, then
        company address) -- just reading the warehouse from the POS config
        instead of a sale order, since there is none here.

        ``delivery.carrier`` is only readable by sales/system users by default
        (see ``delivery/security/ir.model.access.csv``), which a POS cashier
        is not, so the carrier is read with ``sudo()``. Trust is bounded by
        checking it is the carrier actually configured on ``config_id``,
        rather than rating against whatever id the client sends.
        """
        config = self.env['pos.config'].browse(config_id).exists()
        carrier = config.sudo().delivery_carrier_id
        partner = self.env['res.partner'].browse(partner_id).exists()
        if not config or not partner or not carrier or carrier.id != carrier_id:
            return {
                'success': False,
                'price': 0.0,
                'error_message': _("Delivery method or address not found."),
                'warning_message': False,
                'distance_km': False,
            }
        origin_partner = (
            carrier.distance_origin_partner_id
            or (config.warehouse_id and config.warehouse_id.partner_id)
            or config.company_id.partner_id
        )
        return carrier.sudo()._distance_rate_for_partner(partner, origin_partner)
