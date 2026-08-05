# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCityKsa(models.Model):
    """Saudi city lookup data, used to populate the "الحي" city dropdown on
    the portal/eCommerce delivery address form, filtered by the selected
    region (``state_id``). Not linked from ``res.partner``: the form writes
    the selected city's name as plain text into the standard ``city`` field,
    same as before this model existed.
    """
    _name = 'res.city.ksa'
    _description = 'Saudi City (National Address)'
    _order = 'name'

    name = fields.Char(required=True)
    name_en = fields.Char(string='English Name')
    state_id = fields.Many2one('res.country.state', required=True, ondelete='cascade')

    def _get_cities_by_state_json(self):
        """Return {state_id: [city_name, ...]} for every Saudi city, for
        embedding into the delivery address form so JS can filter the city
        dropdown by the selected region without extra RPC calls."""
        result = {}
        for row in self.search_read([], ['state_id', 'name']):
            result.setdefault(row['state_id'][0], []).append(row['name'])
        return result
