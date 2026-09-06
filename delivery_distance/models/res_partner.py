# -*- coding: utf-8 -*-
from odoo import api, models

_DISTANCE_TRIGGER_FIELDS = {
    'partner_latitude', 'partner_longitude',
    'street', 'street2', 'city', 'state_id', 'zip', 'country_id',
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_frontend_writable_fields(self):

        writable_fields = super()._get_frontend_writable_fields()
        return writable_fields | {'partner_latitude', 'partner_longitude'}

    def write(self, vals):
        res = super().write(vals)

        if (
            (_DISTANCE_TRIGGER_FIELDS & vals.keys())
            and not self.env.context.get('distance_recomputing')
        ):
            orders = self.env['sale.order'].sudo().search([
                ('partner_shipping_id', 'in', self.ids),
                ('state', 'in', ('draft', 'sent')),
            ])
            if orders:
                orders._distance_recompute_delivery()
        return res
