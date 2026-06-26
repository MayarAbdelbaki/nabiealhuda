# -*- coding: utf-8 -*-
from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_frontend_writable_fields(self):
        """Allow the geo coordinates to be saved from the frontend forms.

        Odoo 19 routes both the portal ``/my/account`` form and the eCommerce
        ``/shop/address`` form through ``CustomerPortal._parse_form_data``,
        which only persists a submitted key when it is a real partner field
        *and* part of this whitelist. Adding the latitude/longitude here lets
        the location picked on the checkout map reach ``partner.write()`` so the
        distance-based delivery method can price the order.
        """
        writable_fields = super()._get_frontend_writable_fields()
        return writable_fields | {'partner_latitude', 'partner_longitude'}

    def write(self, vals):
        res = super().write(vals)
        # When a shipping address is moved on the map, re-rate the draft orders
        # that deliver to it so the distance-based price stays in sync.
        if (
            ('partner_latitude' in vals or 'partner_longitude' in vals)
            and not self.env.context.get('distance_recomputing')
        ):
            orders = self.env['sale.order'].sudo().search([
                ('partner_shipping_id', 'in', self.ids),
                ('state', 'in', ('draft', 'sent')),
            ])
            if orders:
                orders._distance_recompute_delivery()
        return res
