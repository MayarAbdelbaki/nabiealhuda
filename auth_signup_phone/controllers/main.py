# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo.http import request

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.web.controllers.home import SIGN_UP_REQUEST_PARAMS

# Keep the mobile number typed on the signup form (also refills it when the form shows an error).
SIGN_UP_REQUEST_PARAMS.add('mobile')


class PhoneAuthSignupHome(AuthSignupHome):

    def _prepare_signup_values(self, qcontext):
        values = super()._prepare_signup_values(qcontext)
        number = (qcontext.get('mobile') or '').strip()
        if number:
            values['phone'] = self._signup_phone(number)
        return values

    def _signup_phone(self, number):
        """ Return the number in international format when it is valid, as typed otherwise. """
        Partner = request.env['res.partner'].sudo()
        country = request.env.company.country_id
        # Also accept international numbers typed without + (966...) or with 00 (00966...)
        international = '+' + re.sub(r'\D', '', number).removeprefix('00')
        return (
            Partner._phone_format(number=number, country=country, force_format='INTERNATIONAL')
            or Partner._phone_format(number=international, country=country, force_format='INTERNATIONAL')
            or number
        )
