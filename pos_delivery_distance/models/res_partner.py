# -*- coding: utf-8 -*-
from odoo import _, api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        return fields + ['x_national_address']

    @api.model
    def action_pos_get_delivery_address(self, config_id, partner_id, address_vals):
        """Find or create a delivery-type child contact for the POS 'Delivery' button.

        ``address_vals`` holds the fields typed by the cashier (street, street2,
        city, zip, state_id, country_id, phone, x_national_address). A child
        contact of ``partner_id`` already matching street/city/zip/country is
        reused (and refreshed with the latest values) instead of creating a
        duplicate address every time the same customer orders delivery again;
        otherwise a new one is created.

        Returns the address in the same ``{model: [records]}`` shape as
        ``res.partner.get_new_partner``, so the caller can pass it straight to
        ``data.callRelated`` and get back a live client-side record.
        """
        config = self.env['pos.config'].browse(config_id)
        parent = self.browse(partner_id).exists()
        if not parent:
            return {'res.partner': []}

        vals = {
            'street': (address_vals.get('street') or '').strip(),
            'street2': (address_vals.get('street2') or '').strip(),
            'city': (address_vals.get('city') or '').strip(),
            'zip': (address_vals.get('zip') or '').strip(),
            'phone': (address_vals.get('phone') or '').strip(),
            'x_national_address': (address_vals.get('x_national_address') or '').strip(),
            'state_id': address_vals.get('state_id') or False,
            'country_id': address_vals.get('country_id') or False,
        }

        address = self.search([
            ('parent_id', '=', parent.id),
            ('type', '=', 'delivery'),
            ('street', '=', vals['street']),
            ('city', '=', vals['city']),
            ('zip', '=', vals['zip']),
            ('country_id', '=', vals['country_id']),
        ], limit=1)

        if address:
            address.write(vals)
        else:
            vals.update({
                'type': 'delivery',
                'parent_id': parent.id,
                'name': _("Delivery - %s", vals['street'] or vals['city'] or parent.name),
                'company_id': parent.company_id.id,
            })
            address = self.create(vals)

        return {'res.partner': self._load_pos_data_read(address, config)}
