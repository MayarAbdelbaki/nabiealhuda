# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _msegat_number(self, country=None, number=None):
        """ Return `number`, by default the partner's phone, in the format Msegat expects (e.g. 9665XXXXXXXX).

        :param country: country used for local numbers when the partner has none
        :return: the formatted number, or False when it is not a valid phone number
        """
        self.ensure_one()
        number = number or self.phone
        if not number:
            return False
        country = self.country_id or country
        # Also accept international numbers typed without + (966...) or with 00 (00966...)
        international = '+' + re.sub(r'\D', '', number).removeprefix('00')
        formatted = (
            self._phone_format(number=number, country=country)
            or self._phone_format(number=international, country=country)
        )
        return re.sub(r'\D', '', formatted) if formatted else False
