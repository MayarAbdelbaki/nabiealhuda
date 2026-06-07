# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MyFatoorahSyncWizard(models.TransientModel):
    _name = 'myfatoorah.sync.wizard'
    _description = 'MyFatoorah Manual Status Sync'

    transaction_id = fields.Many2one('payment.transaction', required=True, readonly=True)
    current_status = fields.Char(related='transaction_id.myfatoorah_invoice_status', readonly=True)
    current_state = fields.Selection(related='transaction_id.state', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tx_id = self.env.context.get('active_id')
        if tx_id:
            res['transaction_id'] = tx_id
        return res

    def action_sync(self):
        self.ensure_one()
        tx = self.transaction_id
        if tx.provider_code != 'myfatoorah':
            raise UserError(_('Only for MyFatoorah transactions.'))
        if not tx.myfatoorah_payment_id and not tx.myfatoorah_invoice_id:
            raise UserError(_('No MyFatoorah Payment ID or Invoice ID found on this transaction.'))
        try:
            tx._mf_sync_status()
        except Exception as e:
            raise UserError(str(e))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sync Complete'),
                'message': _('Transaction status refreshed from MyFatoorah. New state: %s', tx.state),
                'type': 'success', 'sticky': False,
            },
        }
