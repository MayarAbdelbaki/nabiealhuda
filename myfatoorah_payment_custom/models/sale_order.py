# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _send_order_confirmation_mail(self):
        """Queue the order-confirmation email instead of sending it inline.

        By default Odoo sends this email synchronously over SMTP while
        confirming the order. That confirmation happens inside the
        ``/payment/status/poll`` request (and the equivalent flow for cash on
        delivery / wire), so if the SMTP server is slow or unreachable the
        request blocks for the full SMTP timeout (~60s). The customer is then
        stuck on the "please wait" payment-status page until it gives up.

        Setting ``mail_notify_force_send=False`` makes the notification a queued
        outgoing ``mail.mail`` that the "Mail: Email Queue Manager" cron delivers
        in the background. The order is still confirmed immediately and the
        customer is redirected to the confirmation page right away. This applies
        to *every* payment method, since they all funnel through this method.
        """
        return super(
            SaleOrder,
            self.with_context(mail_notify_force_send=False, force_send=False),
        )._send_order_confirmation_mail()
