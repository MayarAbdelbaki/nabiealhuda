# -*- coding: utf-8 -*-
"""
MyFatoorah Controller — Full Edition v3
Handles:
  /payment/myfatoorah/return   — customer redirect after payment (success)
  /payment/myfatoorah/error    — customer redirect after failed/cancelled payment
  /payment/myfatoorah/webhook  — server-to-server Webhook v2 (myfatoorah-signature)
"""
import hashlib
import hmac
import json
import logging
import pprint

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MF_SIG_HEADER = 'myfatoorah-signature'


def _mf_resolve_tx(tx_sudo, payment_id, invoice_id='', reference=''):
    """
    Smart transaction resolver.
    Priority: paymentId match → v2 API resolve → invoiceId → reference
    Returns: payment.transaction record or empty recordset
    """
    # Priority 1: exact paymentId match
    if payment_id:
        tx = tx_sudo.search([
            ('provider_code', '=', 'myfatoorah'),
            ('myfatoorah_payment_id', '=', payment_id),
        ], limit=1)
        if tx:
            return tx

    # Priority 2: resolve via MF getPaymentStatus API
    if payment_id:
        try:
            provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'myfatoorah'),
                ('state', 'in', ['enabled', 'test']),
            ], limit=1)
            if provider:
                mf_data = provider._mf_request(
                    'getPaymentStatus',
                    {'Key': payment_id, 'KeyType': 'PaymentId'}
                )
                real_invoice_id = str(mf_data.get('InvoiceId', ''))
                real_ref = mf_data.get('CustomerReference', '')
                _logger.info('MF resolve: paymentId=%s → invoiceId=%s ref=%s',
                             payment_id, real_invoice_id, real_ref)

                if real_invoice_id:
                    tx = tx_sudo.search([
                        ('provider_code', '=', 'myfatoorah'),
                        ('myfatoorah_invoice_id', '=', real_invoice_id),
                        ('state', 'in', ['draft', 'pending']),
                    ], order='create_date desc', limit=1)
                    if tx:
                        return tx

                if real_ref:
                    tx = tx_sudo.search([
                        ('provider_code', '=', 'myfatoorah'),
                        ('reference', '=', real_ref),
                        ('state', 'in', ['draft', 'pending']),
                    ], order='create_date desc', limit=1)
                    if tx:
                        return tx
        except Exception as e:
            _logger.error('MF resolve via API failed: %s', str(e))

    # Priority 3: fallback to URL params
    if reference:
        tx = tx_sudo.search([
            ('provider_code', '=', 'myfatoorah'),
            ('reference', '=', reference),
            ('state', 'in', ['draft', 'pending']),
        ], order='create_date desc', limit=1)
        if tx:
            return tx

    if invoice_id:
        tx = tx_sudo.search([
            ('provider_code', '=', 'myfatoorah'),
            ('myfatoorah_invoice_id', '=', invoice_id),
            ('state', 'in', ['draft', 'pending']),
        ], order='create_date desc', limit=1)
        if tx:
            return tx

    return tx_sudo.browse()


class MyFatoorahController(http.Controller):

    @http.route(
        '/payment/myfatoorah/return',
        type='http', auth='public',
        methods=['GET', 'POST'], csrf=False, save_session=False,
    )
    def myfatoorah_return(self, **data):
        """Customer redirected here after successful payment."""
        _logger.info('MF return: %s', pprint.pformat(data))

        payment_id = data.get('paymentId') or data.get('PaymentId', '')
        invoice_id = data.get('InvoiceId') or data.get('invoiceId', '')
        reference = data.get('customerReference') or data.get('CustomerReference', '')

        try:
            tx_sudo = request.env['payment.transaction'].sudo()
            tx = _mf_resolve_tx(tx_sudo, payment_id, invoice_id, reference)

            if tx:
                _logger.info('MF return: found tx %s, syncing', tx.reference)
                if payment_id:
                    tx.write({'myfatoorah_payment_id': payment_id})
                tx._mf_sync_status()
                _logger.info('MF return: tx %s state=%s', tx.reference, tx.state)
            else:
                _logger.error('MF return: no tx found for paymentId=%s', payment_id)
        except Exception as e:
            _logger.error('MF return error: %s', str(e), exc_info=True)

        return request.redirect('/payment/status')

    @http.route(
        '/payment/myfatoorah/error',
        type='http', auth='public',
        methods=['GET', 'POST'], csrf=False, save_session=False,
    )
    def myfatoorah_error(self, **data):
        """Customer redirected here after failed/cancelled payment."""
        _logger.info('MF error: %s', pprint.pformat(data))

        payment_id = data.get('paymentId') or data.get('PaymentId', '')
        invoice_id = data.get('InvoiceId') or data.get('invoiceId', '')
        reference = data.get('customerReference') or data.get('CustomerReference', '')

        try:
            tx_sudo = request.env['payment.transaction'].sudo()
            tx = _mf_resolve_tx(tx_sudo, payment_id, invoice_id, reference)

            if tx:
                _logger.info('MF error: found tx %s, marking cancelled', tx.reference)
                if payment_id:
                    tx.write({'myfatoorah_payment_id': payment_id})
                tx._mf_sync_status()
                _logger.info('MF error: tx %s state=%s', tx.reference, tx.state)
            else:
                _logger.error('MF error: no tx found for paymentId=%s', payment_id)
        except Exception as e:
            _logger.error('MF error handler exception: %s', str(e), exc_info=True)

        return request.redirect('/payment/status')

    @http.route(
        '/payment/myfatoorah/webhook',
        type='http', auth='public',
        methods=['POST'], csrf=False, save_session=False,
    )
    def myfatoorah_webhook(self, **kwargs):
        """Real-time server-to-server webhook from MyFatoorah."""
        raw_body = request.httprequest.get_data(as_text=False)
        signature = request.httprequest.headers.get(MF_SIG_HEADER, '')

        _logger.info('MF webhook: %d bytes, sig=%s', len(raw_body),
                     signature[:20] if signature else 'NONE')

        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.error('MF webhook bad body: %s', str(e))
            return request.make_response('Bad Request', status=400)

        providers = request.env['payment.provider'].sudo().search([
            ('code', '=', 'myfatoorah'),
            ('state', 'in', ['enabled', 'test']),
        ])

        processed = False
        for provider in providers:
            if provider.myfatoorah_webhook_secret:
                if not self._mf_verify_signature(
                        raw_body, signature, provider.myfatoorah_webhook_secret):
                    _logger.warning('MF webhook: invalid signature for provider %s', provider.id)
                    continue
            try:
                self._mf_process_webhook(payload)
                processed = True
                break
            except Exception as e:
                _logger.error('MF webhook processing error: %s', str(e))

        if not processed and not providers.filtered(lambda p: p.myfatoorah_webhook_secret):
            try:
                self._mf_process_webhook(payload)
            except Exception as e:
                _logger.error('MF webhook (no secret): %s', str(e))

        return request.make_response('OK', status=200)

    def _mf_verify_signature(self, raw_body, signature, secret):
        try:
            expected = hmac.new(
                secret.encode('utf-8'), raw_body, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected.lower(), (signature or '').lower())
        except Exception as e:
            _logger.error('MF sig verify error: %s', str(e))
            return False

    def _mf_process_webhook(self, payload):
        event = payload.get('Event', '')
        data = payload.get('Data', {})

        if event not in ('Payment', 'Refund', 'Recurring'):
            _logger.info('MF webhook: ignoring event "%s"', event)
            return

        invoice_data = data.get('Invoice', {})
        tx_data = data.get('Transaction', {})

        invoice_id = str(invoice_data.get('Id', '') or data.get('InvoiceId', ''))
        payment_id = str(tx_data.get('PaymentId', '') or data.get('PaymentId', ''))
        reference = str(invoice_data.get('Reference', '') or data.get('CustomerReference', ''))

        tx_sudo = request.env['payment.transaction'].sudo()
        tx = _mf_resolve_tx(tx_sudo, payment_id, invoice_id, reference)

        if not tx:
            _logger.error('MF webhook: no tx found for event=%s paymentId=%s', event, payment_id)
            return

        if payment_id:
            tx.write({'myfatoorah_payment_id': payment_id})
        tx._mf_sync_status()

        _logger.info('MF webhook processed: event=%s tx=%s state=%s',
                     event, tx.reference, tx.state)
