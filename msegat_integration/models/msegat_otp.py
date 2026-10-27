# Part of Odoo. See LICENSE file for full copyright and licensing details.

import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.misc import hmac

from odoo.addons.msegat_integration import const


class MsegatOtp(models.Model):
    _name = 'msegat.otp'
    _description = "Msegat Verification Code"
    _order = 'id desc'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string="User", required=True, readonly=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string="Company", required=True, readonly=True, ondelete='cascade')
    number = fields.Char(string="Mobile Number", required=True, readonly=True)
    method = fields.Selection(
        selection=[('api', "Msegat OTP service"), ('sms', "Odoo code by SMS")],
        string="Method",
        required=True,
        readonly=True,
    )
    msegat_code_id = fields.Char(string="Msegat Code ID", readonly=True, copy=False)
    code_hash = fields.Char(groups=fields.NO_ACCESS, copy=False)
    ip = fields.Char(string="IP Address", readonly=True)
    attempts = fields.Integer(string="Attempts", readonly=True)
    state = fields.Selection(
        selection=[('sent', "Sent"), ('verified', "Verified"), ('failed', "Too Many Attempts")],
        string="Status",
        default='sent',
        required=True,
        readonly=True,
    )

    @api.model
    def _send_code(self, user, new_number=False):
        """ Send a new verification code by SMS to `user`'s phone number.

        :param new_number: number typed by the user instead of the one on file
        :return: the created `msegat.otp` record
        :raise UserError: when the code cannot be sent
        """
        user = user.sudo()
        company = user.company_id
        number = new_number or user._msegat_otp_number()
        if not number:
            raise UserError(_("Enter your mobile number to receive the verification code."))
        if self.search_count([
            ('user_id', '=', user.id),
            ('create_date', '>=', fields.Datetime.now() - timedelta(hours=1)),
        ]) >= const.OTP_SEND_LIMIT:
            raise UserError(_("Too many verification codes were requested for your account. Please try again later."))

        otp = self.create({
            'user_id': user.id,
            'company_id': company.id,
            'number': number,
            'method': company.msegat_otp_method,
            'ip': request.httprequest.remote_addr if request else False,
        })
        if otp.method == 'api':
            otp.msegat_code_id = company._msegat_send_otp(number)
        else:
            code = str(secrets.randbelow(10 ** const.OTP_CODE_LENGTH)).zfill(const.OTP_CODE_LENGTH)
            otp.code_hash = otp._hash_code(code)
            company._msegat_send_sms(number, company.msegat_otp_message.replace('{code}', code))
        return otp

    def _hash_code(self, code):
        self.ensure_one()
        return hmac(self.env(su=True), 'msegat_integration-otp', (self.id, code))

    def _is_pending(self):
        self.ensure_one()
        return self.state == 'sent' and fields.Datetime.now() < self.create_date + timedelta(minutes=const.OTP_VALIDITY_MINUTES)

    def _verify(self, code):
        """ Check `code` against this verification code, which can be used only once.

        :return: whether the code is valid
        """
        self.ensure_one()
        code = (code or '').strip()
        if not code or not self._is_pending():
            return False
        self.attempts += 1
        if self.method == 'api':
            valid = self.company_id._msegat_verify_otp(self.msegat_code_id, code)
        else:
            valid = consteq(self.sudo().code_hash or '', self._hash_code(code))
        if valid:
            self.state = 'verified'
        elif self.attempts >= const.OTP_MAX_ATTEMPTS:
            self.state = 'failed'
        return valid

    def _masked_number(self):
        self.ensure_one()
        return f"+{'•' * (len(self.number) - 4)}{self.number[-4:]}"

    @api.autovacuum
    def _gc_login_codes(self):
        self.search([('create_date', '<', fields.Datetime.now() - timedelta(days=30))]).unlink()
