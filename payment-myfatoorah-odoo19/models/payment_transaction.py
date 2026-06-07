# -*- coding: utf-8 -*-
"""
MyFatoorah Payment Transaction — Full Edition v3
Handles: redirect → v3/v2 validation → auto-update invoices & orders → failure detection
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .payment_provider import MF_STATUS_MAP

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # ── MyFatoorah tracking fields ────────────────────────────────────────────
    myfatoorah_invoice_id = fields.Char(string='MF Invoice ID', readonly=True)
    myfatoorah_payment_id = fields.Char(string='MF Payment ID', readonly=True)
    myfatoorah_payment_method = fields.Char(string='Payment Method', readonly=True)
    myfatoorah_invoice_status = fields.Char(string='MF Status', readonly=True)
    myfatoorah_card_token = fields.Char(string='Card Token (KFast)', readonly=True)
    myfatoorah_card_brand = fields.Char(string='Card Brand', readonly=True)
    myfatoorah_card_last4 = fields.Char(string='Card Last 4', readonly=True)
    myfatoorah_error_code = fields.Char(string='MF Error Code', readonly=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 — Render redirect form to MF hosted payment page
    # ─────────────────────────────────────────────────────────────────────────

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'myfatoorah':
            return res

        provider = self.provider_id
        token = self.token_id

        if token and token.myfatoorah_token:
            payment_data = provider._mf_execute_payment(self, token=token.myfatoorah_token)
        else:
            payment_data = provider._mf_execute_payment(self)

        invoice_id = payment_data.get('InvoiceId')
        invoice_url = payment_data.get('InvoiceURL')

        if not invoice_url and not token:
            raise ValidationError(_('MyFatoorah returned no payment URL. Please try again.'))

        self.sudo().write({'myfatoorah_invoice_id': str(invoice_id) if invoice_id else ''})
        _logger.info('MF: created invoice %s for tx %s', invoice_id, self.reference)

        return {'api_url': invoice_url or ''}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2 — Match notification data to transaction (webhook/return URL)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != 'myfatoorah':
            if hasattr(super(), '_get_tx_from_notification_data'):
                return super()._get_tx_from_notification_data(provider_code, notification_data)
            return self.env['payment.transaction']

        reference = (notification_data.get('CustomerReference')
                     or notification_data.get('customerReference', ''))
        invoice_id = (notification_data.get('InvoiceId')
                      or notification_data.get('invoiceId', ''))
        payment_id = (notification_data.get('PaymentId')
                      or notification_data.get('paymentId', ''))

        domain = [('provider_code', '=', 'myfatoorah')]
        tx = self.env['payment.transaction']

        if reference:
            tx = self.search(domain + [('reference', '=', reference)])
        if not tx and invoice_id:
            tx = self.search(domain + [('myfatoorah_invoice_id', '=', str(invoice_id))])
        if not tx and payment_id:
            tx = self.search(domain + [('myfatoorah_payment_id', '=', str(payment_id))])

        if not tx:
            raise ValidationError(
                _('MyFatoorah: no transaction found for ref=%s / invoiceId=%s / paymentId=%s',
                  reference, invoice_id, payment_id)
            )
        return tx

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3 — Validate server-side (called from _handle_notification_data)
    # ─────────────────────────────────────────────────────────────────────────

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != 'myfatoorah':
            return

        payment_id = (notification_data.get('PaymentId')
                      or notification_data.get('paymentId')
                      or self.myfatoorah_payment_id)

        if payment_id:
            self._mf_validate_via_v3(str(payment_id))
        else:
            invoice_id = (notification_data.get('InvoiceId')
                          or notification_data.get('invoiceId')
                          or self.myfatoorah_invoice_id)
            if invoice_id:
                self._mf_validate_via_v2(str(invoice_id))
            else:
                _logger.error('MF: no PaymentId or InvoiceId for tx %s', self.reference)
                self._set_error('MyFatoorah: missing payment identifiers.')

    # ─────────────────────────────────────────────────────────────────────────
    # v3 validation — primary (card details + status)
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_validate_via_v3(self, payment_id):
        try:
            data = self.provider_id._mf_get_payment_status_v3(payment_id)
        except Exception as e:
            _logger.error('MF v3 failed for tx %s: %s', self.reference, str(e))
            self._set_error(f'MyFatoorah v3 error: {str(e)}')
            return

        # Supplement with v2 to get InvoiceTransactions list for failure detection
        try:
            invoice_key = self.myfatoorah_invoice_id or payment_id
            v2_data = self.provider_id._mf_get_payment_status_v2(invoice_key)
            if isinstance(v2_data, dict):
                if 'InvoiceTransactions' not in data:
                    data['InvoiceTransactions'] = v2_data.get('InvoiceTransactions', [])
                if 'InvoiceStatus' not in data:
                    data['InvoiceStatus'] = v2_data.get('InvoiceStatus', '')
        except Exception as e:
            _logger.warning('MF v2 supplement failed (non-fatal): %s', str(e))

        # Extract fields
        invoice = data.get('Invoice', {})
        transaction = data.get('Transaction', {})
        card = transaction.get('Card', {})

        mf_status = (invoice.get('Status') or data.get('InvoiceStatus', '')).upper()
        tx_status = transaction.get('Status', '').upper()
        mf_payment_id = transaction.get('PaymentId', payment_id)
        payment_method = transaction.get('PaymentMethod', '')
        card_token = card.get('Token', '')
        card_brand = card.get('Brand', '')
        card_number = card.get('Number', '')
        error_code = ''
        try:
            error_code = transaction.get('Error', {}).get('Code', '')
        except Exception:
            pass

        last4 = card_number[-4:] if card_number and len(card_number) >= 4 else ''

        vals = {
            'myfatoorah_payment_id': str(mf_payment_id),
            'myfatoorah_invoice_status': mf_status,
            'myfatoorah_payment_method': payment_method,
            'myfatoorah_error_code': error_code,
        }
        if card_brand:
            vals['myfatoorah_card_brand'] = card_brand
        if last4:
            vals['myfatoorah_card_last4'] = last4
        if card_token:
            vals['myfatoorah_card_token'] = card_token

        self.sudo().write(vals)

        _logger.info('MF v3: tx=%s status=%s tx_status=%s method=%s paymentId=%s',
                     self.reference, mf_status, tx_status, payment_method, mf_payment_id)

        if card_token and self.provider_id.myfatoorah_enable_kfast and self.tokenize:
            self._mf_save_token(card_token, card_brand, last4)

        # ── Failure detection via InvoiceTransactions ──────────────────────
        transactions = data.get('InvoiceTransactions') or []
        has_success = any(
            str(t.get('TransactionStatus', '')).lower()
            in ('success', 'successful', 'captured', 'succss')
            for t in transactions
        )
        has_failure = any(
            str(t.get('TransactionStatus', '')).lower()
            in ('failed', 'cancelled', 'canceled', 'declined')
            for t in transactions
        )

        if transactions and not has_success and has_failure:
            latest_failed = next(
                (t for t in reversed(transactions)
                 if str(t.get('TransactionStatus', '')).lower()
                 in ('failed', 'cancelled', 'canceled', 'declined')),
                {}
            )
            err_msg = latest_failed.get('Error', 'Payment failed')
            err_code = latest_failed.get('ErrorCode', '')
            self.sudo().write({
                'myfatoorah_error_code': err_code,
                'myfatoorah_invoice_status': 'FAILED',
            })
            _logger.warning('MF: tx %s FAILED — error=%s code=%s',
                            self.reference, err_msg, err_code)
            if self.state not in ('cancel', 'error', 'done'):
                self._set_canceled(
                    state_message=f'MyFatoorah: {err_msg} ({err_code})')
            return

        self._mf_apply_status(mf_status, tx_status)

    # ─────────────────────────────────────────────────────────────────────────
    # v2 fallback — when only InvoiceId is available
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_validate_via_v2(self, invoice_id):
        try:
            data = self.provider_id._mf_get_payment_status_v2(invoice_id)
        except Exception as e:
            _logger.error('MF v2 fallback failed for tx %s: %s', self.reference, str(e))
            self._set_error(f'MyFatoorah validation error: {str(e)}')
            return

        invoice_status = data.get('InvoiceStatus', '')
        transactions = data.get('InvoiceTransactions', [])
        paid_tx = next(
            (t for t in transactions
             if str(t.get('TransactionStatus', '')).lower() in ('successful', 'success')),
            transactions[0] if transactions else {},
        )
        payment_id = paid_tx.get('PaymentId', '')
        method = paid_tx.get('PaymentGateway', '')

        self.sudo().write({
            'myfatoorah_invoice_id': str(invoice_id),
            'myfatoorah_payment_id': str(payment_id),
            'myfatoorah_invoice_status': invoice_status,
            'myfatoorah_payment_method': method,
        })

        if payment_id:
            self._mf_validate_via_v3(str(payment_id))
        else:
            self._mf_apply_status(invoice_status, '')

    # ─────────────────────────────────────────────────────────────────────────
    # Status → Odoo state mapping
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_apply_status(self, mf_status, tx_status=''):
        status_upper = (mf_status or '').upper()
        tx_upper = (tx_status or '').upper()

        # Priority 1: tx-level failure always wins
        if tx_upper in ('FAILED', 'CANCELLED', 'CANCELED', 'DECLINED', 'ERROR', 'REJECTED'):
            odoo_state = 'cancel'
        # Priority 2: invoice-level success
        elif status_upper in ('PAID', 'SUCCESS') or tx_upper == 'SUCCESS':
            odoo_state = 'done'
        # Priority 3: invoice-level failure
        elif status_upper in ('FAILED', 'CANCELED', 'EXPIRED', 'DECLINED'):
            odoo_state = 'cancel'
        # Priority 4: in-progress
        elif status_upper in ('PENDING', 'INPROGRESS', 'AUTHORIZE') or \
                tx_upper in ('INPROGRESS', 'AUTHORIZE'):
            odoo_state = 'pending'
        else:
            odoo_state = MF_STATUS_MAP.get(mf_status, 'pending')

        if odoo_state == 'done':
            self._set_done()
            self._mf_update_documents_on_success()
        elif odoo_state == 'pending':
            self._set_pending()
        elif odoo_state == 'cancel':
            self._set_canceled(state_message=f'MyFatoorah: {mf_status or tx_status}')

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-update linked Odoo documents on payment success
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_update_documents_on_success(self):
        self.ensure_one()

        # Invoices
        for invoice in self.invoice_ids:
            if invoice.state == 'draft':
                invoice.action_post()
            if invoice.payment_state not in ('paid', 'in_payment'):
                try:
                    self._reconcile_after_done()
                except Exception as e:
                    _logger.warning('MF: invoice reconcile for %s: %s', invoice.name, str(e))
            _logger.info('MF: invoice %s → payment registered', invoice.name)

        # Sales Orders
        if hasattr(self, 'sale_order_ids'):
            for order in self.sale_order_ids:
                if order.state == 'draft':
                    order.action_confirm()
                _logger.info('MF: sale order %s → confirmed / payment done', order.name)

        # Subscriptions (Enterprise)
        if hasattr(self, 'subscription_ids'):
            for sub in getattr(self, 'subscription_ids', []):
                if hasattr(sub, 'stage_category') and sub.stage_category != 'progress':
                    try:
                        sub.write({'stage_id': sub._get_default_stage_id().id})
                    except Exception as e:
                        _logger.warning('MF: subscription update: %s', str(e))

        # Receipt email
        if self.provider_id.myfatoorah_send_invoice_email and self.partner_id.email:
            try:
                template = self.env.ref(
                    'payment_myfatoorah.email_template_payment_receipt',
                    raise_if_not_found=False,
                )
                if template:
                    template.send_mail(self.id, force_send=True)
            except Exception as e:
                _logger.warning('MF: receipt email failed: %s', str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Manual sync (called from cron + return/error handlers)
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_sync_status(self):
        self.ensure_one()
        if self.myfatoorah_payment_id:
            self._mf_validate_via_v3(self.myfatoorah_payment_id)
        elif self.myfatoorah_invoice_id:
            self._mf_validate_via_v2(self.myfatoorah_invoice_id)

    # ─────────────────────────────────────────────────────────────────────────
    # KFast tokenization (saved cards for subscriptions)
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_save_token(self, card_token, card_brand, last4):
        existing = self.env['payment.token'].sudo().search([
            ('provider_id', '=', self.provider_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('myfatoorah_token', '=', card_token),
        ], limit=1)
        if not existing:
            self.env['payment.token'].sudo().create({
                'provider_id': self.provider_id.id,
                'partner_id': self.partner_id.id,
                'payment_method_id': self.payment_method_id.id,
                'provider_ref': card_token,
                'myfatoorah_token': card_token,
                'myfatoorah_card_brand': card_brand,
                'myfatoorah_card_last4': last4,
                'active': True,
            })
            _logger.info('MF: saved KFast token for partner %s', self.partner_id.name)

    # ─────────────────────────────────────────────────────────────────────────
    # Refund
    # ─────────────────────────────────────────────────────────────────────────

    def _send_refund_request(self, amount_to_refund=None):
        child_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'myfatoorah':
            return child_tx

        payment_id = self.myfatoorah_payment_id
        if not payment_id:
            raise ValidationError(_('MyFatoorah Payment ID missing. Cannot refund.'))

        amount = amount_to_refund or self.amount
        try:
            self.provider_id._mf_refund(payment_id, amount, 'Refund via Odoo')
            _logger.info('MF: refund issued PaymentId=%s amount=%s', payment_id, amount)
            if child_tx:
                child_tx._set_done()
        except Exception as e:
            _logger.error('MF: refund failed: %s', str(e))
            if child_tx:
                child_tx._set_error(str(e))
            raise

        return child_tx
