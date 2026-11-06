# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.web.controllers.home import SIGN_UP_REQUEST_PARAMS

# Keep the mobile number typed on the signup form (also refills it when the form shows an error).
SIGN_UP_REQUEST_PARAMS.add('mobile')

# Saudi mobile numbers: +966 5X XXX XXXX
SAUDI_MOBILE_RE = re.compile(r'^\+9665\d{8}$')


class PhoneAuthSignupHome(AuthSignupHome):

    @http.route()
    def web_auth_signup(self, *args, **kw):
        # Do not make the customer wait for the SMTP server to send the "account created" email.
        # Flag set on the request, not the context: logging in the new user resets the context.
        request.signup_send_mail_in_background = True
        return super().web_auth_signup(*args, **kw)

    def _prepare_signup_values(self, qcontext):
        values = super()._prepare_signup_values(qcontext)
        number = (qcontext.get('mobile') or '').strip()
        if number:
            values['phone'] = self._signup_phone(number)
        return values

    def _signup_phone(self, number):
        """ Return the number as a Saudi mobile number in international format.

        Accepts 05XXXXXXXX, 5XXXXXXXX, +9665XXXXXXXX, 9665XXXXXXXX and 009665XXXXXXXX.

        :raise UserError: when the number is not a valid Saudi mobile number
        """
        Partner = request.env['res.partner'].sudo()
        saudi_arabia = request.env.ref('base.sa')
        digits = re.sub(r'\D', '', number).removeprefix('00')
        candidates = [number, '+' + digits] if digits.startswith('966') else [number]
        for candidate in candidates:
            e164 = Partner._phone_format(number=candidate, country=saudi_arabia, force_format='E164')
            if e164 and SAUDI_MOBILE_RE.match(e164):
                return Partner._phone_format(number=e164, country=saudi_arabia, force_format='INTERNATIONAL')
        raise UserError(request.env._(
            "Please enter a valid Saudi mobile number, for example 05XXXXXXXX.",
        ))
