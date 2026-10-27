# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    msegat_verify_phone = fields.Boolean(
        string="Phone Verification Pending",
        copy=False,
        help="At their next login, the user must confirm their phone number with a code sent by SMS. "
             "Set on external users created while the phone verification is enabled.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.filtered(
            lambda user: user.company_id.msegat_otp_login and not user._is_internal()
        ).msegat_verify_phone = True
        return users

    def _mfa_type(self):
        r = super()._mfa_type()
        if r is not None:
            return r
        if self._msegat_otp_required():
            return 'msegat_otp'

    def _mfa_url(self):
        r = super()._mfa_url()
        if r is not None:
            return r
        if self._mfa_type() == 'msegat_otp':
            return '/web/login/msegat_otp'

    def _msegat_otp_required(self):
        self.ensure_one()
        user = self.sudo()
        return bool(user.msegat_verify_phone and user.company_id.msegat_otp_login and not user._is_internal())

    def _msegat_otp_number(self):
        """ Return the user's phone number in the Msegat format, or False when it is not a valid one. """
        self.ensure_one()
        user = self.sudo()
        return user.partner_id._msegat_number(user.company_id.country_id)

    def _rpc_api_keys_only(self):
        # The SMS code cannot be checked on RPC, so the password alone must not be enough.
        return self._mfa_type() == 'msegat_otp' or super()._rpc_api_keys_only()

    def _check_credentials(self, credential, env):
        if credential['type'] != 'msegat_otp':
            return super()._check_credentials(credential, env)
        user = self.sudo()
        otp = self.env['msegat.otp'].sudo().browse(credential.get('otp_id')).exists()
        if not (otp and otp.user_id == user and otp._verify(credential.get('code'))):
            _logger.info("Msegat phone verification: FAIL for %s %r", user, user.login)
            raise AccessDenied(_("The verification code is invalid or has expired."))
        _logger.info("Msegat phone verification: SUCCESS for %s %r", user, user.login)
        if user._msegat_otp_number() != otp.number:
            user.partner_id.phone = f'+{otp.number}'
        user.msegat_verify_phone = False
        return {
            'uid': user.id,
            'auth_method': 'msegat_otp',
            'mfa': 'default',
        }
