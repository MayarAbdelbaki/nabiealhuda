# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import threading

from odoo import SUPERUSER_ID, api, models
from odoo.http import request
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    def send_mail(self, res_id, force_send=False, raise_exception=False, email_values=None,
                  email_layout_xmlid=False):
        """ During the website signup, send the email in the background instead of making the customer wait
        for the SMTP server. """
        if not (force_send and request and getattr(request, 'signup_send_mail_in_background', False)):
            return super().send_mail(
                res_id, force_send=force_send, raise_exception=raise_exception,
                email_values=email_values, email_layout_xmlid=email_layout_xmlid,
            )
        mail_id = super().send_mail(
            res_id, force_send=False, raise_exception=raise_exception,
            email_values=email_values, email_layout_xmlid=email_layout_xmlid,
        )
        if mail_id:
            self._send_mail_in_background(mail_id)
        return mail_id

    def _send_mail_in_background(self, mail_id):
        """ Send the mail from a new thread once the current transaction is committed. """
        dbname = self.env.cr.dbname
        context = dict(self.env.context)

        def send():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, context)
                    env['mail.mail'].browse(mail_id).exists().send()
            except Exception:
                _logger.exception("Signup: could not send the mail %s", mail_id)

        @self.env.cr.postcommit.add
        def start_thread():
            thread = threading.Thread(target=send, name=f'signup_mail_{mail_id}', daemon=True)
            thread.dbname = dbname
            thread.start()
