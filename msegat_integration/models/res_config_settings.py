# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    msegat_username = fields.Char(related='company_id.msegat_username', readonly=False)
    msegat_api_key = fields.Char(related='company_id.msegat_api_key', readonly=False, groups='base.group_system')
    msegat_sender = fields.Char(related='company_id.msegat_sender', readonly=False)
    msegat_otp_login = fields.Boolean(related='company_id.msegat_otp_login', readonly=False)
    msegat_otp_method = fields.Selection(related='company_id.msegat_otp_method', readonly=False)
    msegat_otp_lang = fields.Selection(related='company_id.msegat_otp_lang', readonly=False)
    msegat_otp_message = fields.Char(related='company_id.msegat_otp_message', readonly=False)
    msegat_whatsapp_url = fields.Char(related='company_id.msegat_whatsapp_url', readonly=False)
    msegat_whatsapp_email = fields.Char(related='company_id.msegat_whatsapp_email', readonly=False)
    msegat_whatsapp_password = fields.Char(
        related='company_id.msegat_whatsapp_password', readonly=False, groups='base.group_system',
    )
    msegat_whatsapp_mode = fields.Selection(related='company_id.msegat_whatsapp_mode', readonly=False)
    msegat_whatsapp_template = fields.Char(related='company_id.msegat_whatsapp_template', readonly=False)
    msegat_whatsapp_template_params = fields.Char(
        related='company_id.msegat_whatsapp_template_params', readonly=False,
    )

    def action_msegat_check_balance(self):
        balance = self.company_id._msegat_get_balance()
        return self._msegat_notification(_("Connected to Msegat. Balance: %s points.", balance))

    def action_msegat_test_whatsapp(self):
        self.company_id._msegat_whatsapp_token(refresh=True)
        return self._msegat_notification(_("Connected to the Msegat WhatsApp API."))

    def _msegat_notification(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'message': message, 'sticky': False},
        }
