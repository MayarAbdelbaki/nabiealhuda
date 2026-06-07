# -*- coding: utf-8 -*-
from odoo import fields, models


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    myfatoorah_token = fields.Char(
        string='MF Card Token',
        help='KFast token from MyFatoorah — used for recurring/subscription payments.',
        groups='base.group_system',
    )
    myfatoorah_card_brand = fields.Char(string='Card Brand', readonly=True)
    myfatoorah_card_last4 = fields.Char(string='Last 4 Digits', readonly=True)

    def _build_display_name(self, *args, **kwargs):
        if self.provider_id.code != 'myfatoorah':
            return super()._build_display_name(*args, **kwargs)
        brand = self.myfatoorah_card_brand or 'Card'
        last4 = self.myfatoorah_card_last4 or '****'
        return f'{brand} •••• {last4}'
