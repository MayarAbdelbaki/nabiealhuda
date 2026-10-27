# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, http
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

from odoo.addons.web.controllers import home as web_home


class Home(web_home.Home):

    @http.route(
        '/web/login/msegat_otp',
        type='http', auth='public', methods=['GET', 'POST'], sitemap=False,
        website=True, multilang=False,
    )
    def web_msegat_otp(self, redirect=None, **kwargs):
        """ Second login step of new external users: they confirm their phone number once with an SMS code. """
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))
        if not request.session.get('pre_uid'):
            return request.redirect('/web/login')

        user = request.env['res.users'].browse(request.session['pre_uid'])
        if user._mfa_type() != 'msegat_otp':
            return request.redirect('/web/login')

        Otp = request.env['msegat.otp'].sudo()
        otp = Otp.browse(request.session.get('msegat_otp_id')).exists().filtered(lambda o: o.user_id == user)
        is_post = request.httprequest.method == 'POST'
        error = None
        if is_post and kwargs.get('otp_code'):
            try:
                with user._assert_can_auth(user=user.id):
                    user._check_credentials(
                        {'type': 'msegat_otp', 'otp_id': otp.id, 'code': kwargs['otp_code']},
                        {'interactive': True},
                    )
            except (AccessDenied, UserError) as e:
                error = str(e)
            else:
                request.session.pop('msegat_otp_id', None)
                request.session.finalize(request.env)
                request.update_env(user=request.session.uid)
                request.update_context(**request.session.context)
                return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))
        elif is_post and kwargs.get('change_number'):
            request.session.pop('msegat_otp_id', None)
            request.session['msegat_otp_change_number'] = True
            otp = Otp
        else:
            send = kwargs.get('resend') or not (otp and otp._is_pending())
            new_number = False
            if is_post and kwargs.get('phone'):
                new_number = user.sudo().partner_id._msegat_number(
                    user.sudo().company_id.country_id, number=kwargs['phone'],
                )
                send = bool(new_number)
                if not new_number:
                    error = _("Please enter a valid mobile number.")
            elif otp:
                new_number = otp.number
            elif request.session.get('msegat_otp_change_number') or not user._msegat_otp_number():
                send = False
            if send:
                try:
                    # Roll back the code when it could not be sent, so it does not count in the limit.
                    with request.env.cr.savepoint():
                        otp = Otp._send_code(user, new_number=new_number)
                    request.session['msegat_otp_id'] = otp.id
                    request.session.pop('msegat_otp_change_number', None)
                except UserError as e:
                    error = str(e)

        # Workaround for the Odoo iOS app, see auth_totp
        request.session.touch()
        return request.render('msegat_integration.login_otp_form', {
            'ask_number': not otp,
            'number': otp and otp._masked_number(),
            'error': error,
            'redirect': redirect,
        })
