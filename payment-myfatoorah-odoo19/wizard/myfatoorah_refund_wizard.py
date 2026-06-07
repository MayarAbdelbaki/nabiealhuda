# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MyFatoorahRefundWizard(models.TransientModel):
    _name = 'myfatoorah.refund.wizard'
    _description = 'MyFatoorah Refund'

    transaction_id = fields.Many2one('payment.transaction', required=True, readonly=True)
    original_amount = fields.Monetary(related='transaction_id.amount', readonly=True)
    currency_id = fields.Many2one(related='transaction_id.currency_id', readonly=True)
    refund_amount = fields.Monetary(currency_field='currency_id', required=True)
    reason = fields.Char(default='Customer refund request')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tx_id = self.env.context.get('active_id')
        if tx_id:
            tx = self.env['payment.transaction'].browse(tx_id)
            res.update({'transaction_id': tx.id, 'refund_amount': tx.amount})
        return res

    def action_refund(self):
        self.ensure_one()
        tx = self.transaction_id
        if tx.provider_code != 'myfatoorah':
            raise UserError(_('Only for MyFatoorah transactions.'))
        if tx.state != 'done':
            raise UserError(_('Only completed transactions can be refunded.'))
        if self.refund_amount <= 0 or self.refund_amount > tx.amount:
            raise UserError(_('Invalid refund amount.'))
        if not tx.myfatoorah_payment_id:
            raise UserError(_('MyFatoorah Payment ID missing — cannot refund.'))
        try:
            tx.provider_id._mf_refund(tx.myfatoorah_payment_id, self.refund_amount, self.reason)
        except ValidationError as e:
            raise UserError(str(e))
        tx.message_post(body=_(
            'Refund: %(amount)s %(currency)s — %(reason)s',
            amount=self.refund_amount, currency=tx.currency_id.name, reason=self.reason,
        ))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Refund Issued'), 'message': _(
                'Refund of %s %s submitted.', self.refund_amount, tx.currency_id.name,
            ), 'type': 'success', 'sticky': False},
        }
