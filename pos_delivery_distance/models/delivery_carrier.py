# -*- coding: utf-8 -*-
from odoo import _, api, models


class DeliveryCarrier(models.Model):
    _inherit = ['delivery.carrier', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data, config):
        carrier = config.delivery_carrier_id
        return [('id', '=', carrier.id)] if carrier else [('id', '=', 0)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name', 'delivery_type', 'product_id']

    @api.model
    def action_pos_rate_delivery(self, carrier_id, partner_id, config_id):
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

        carrier = carrier.sudo()
        if carrier.delivery_type == 'distance_based':
            origin_partner = (
                carrier.distance_origin_partner_id
                or (config.warehouse_id and config.warehouse_id.partner_id)
                or config.company_id.partner_id
            )
            return carrier._distance_rate_for_partner(partner, origin_partner)

        fake_order = self.env['sale.order'].new({
            'partner_id': partner.id,
            'partner_shipping_id': partner.id,
            'company_id': config.company_id.id,
            'warehouse_id': config.warehouse_id.id,
        })
        try:
            result = carrier.rate_shipment(fake_order)
        except Exception as exc:  # noqa: BLE001 -- surface any provider failure as a rate error, not a crash
            return {
                'success': False,
                'price': 0.0,
                'error_message': str(exc) or _("Could not price this delivery method."),
                'warning_message': False,
                'distance_km': False,
            }
        result.setdefault('distance_km', False)
        return result
