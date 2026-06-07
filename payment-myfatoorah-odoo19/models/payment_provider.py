# -*- coding: utf-8 -*-
"""
MyFatoorah Payment Provider — Full Edition v3
Works on Odoo 19 Community and Enterprise.
"""
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ── API endpoints per country ─────────────────────────────────────────────────
MF_ENDPOINTS = {
    'kw': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'Kuwait'},
    'sa': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api-sa.myfatoorah.com', 'label': 'Saudi Arabia'},
    'ae': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'UAE'},
    'bh': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'Bahrain'},
    'qa': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'Qatar'},
    'om': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'Oman'},
    'jo': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api.myfatoorah.com',    'label': 'Jordan'},
    'eg': {'test': 'https://apitest.myfatoorah.com', 'live': 'https://api-eg.myfatoorah.com', 'label': 'Egypt'},
}

# MF invoice/transaction status → Odoo state
MF_STATUS_MAP = {
    'PAID': 'done', 'SUCCESS': 'done', 'PARTIALLYREFUNDED': 'done',
    'PENDING': 'pending', 'INPROGRESS': 'pending', 'AUTHORIZE': 'pending',
    'FAILED': 'cancel', 'CANCELED': 'cancel', 'EXPIRED': 'cancel',
    'DECLINED': 'cancel', 'REFUNDED': 'cancel',
    # v2 capitalisation variants
    'Paid': 'done', 'Failed': 'cancel', 'Expired': 'cancel',
}

MF_CURRENCIES = ['KWD', 'SAR', 'AED', 'BHD', 'QAR', 'OMR', 'JOD', 'EGP', 'USD']


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('myfatoorah', 'MyFatoorah')],
        ondelete={'myfatoorah': 'set default'},
    )

    # ── Credentials ──────────────────────────────────────────────────────────
    myfatoorah_api_token = fields.Char(
        string='API Token',
        required_if_provider='myfatoorah',
        groups='base.group_system',
        help='Bearer token from MyFatoorah Portal → Settings → API Keys.',
    )
    myfatoorah_country = fields.Selection(
        selection=[(k, v['label']) for k, v in MF_ENDPOINTS.items()],
        string='Country / Region',
        default='kw',
        required_if_provider='myfatoorah',
    )
    myfatoorah_webhook_secret = fields.Char(
        string='Webhook Secret Key',
        groups='base.group_system',
        help='Webhook secret from MyFatoorah portal for signature verification.',
    )

    # ── Feature flags ─────────────────────────────────────────────────────────
    myfatoorah_enable_kfast = fields.Boolean(
        string='Enable KFast (Save Card)',
        default=False,
        help='Allow customers to save their card via KFast for future payments.',
    )
    myfatoorah_show_logos = fields.Boolean(
        string='Show Payment Logos on Checkout',
        default=True,
    )
    myfatoorah_send_invoice_email = fields.Boolean(
        string='Send Payment Receipt Email',
        default=True,
    )
    myfatoorah_cron_enabled = fields.Boolean(
        string='Enable Payment Status Polling',
        default=True,
        help='Polls MyFatoorah every 15 minutes for pending transactions.',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Core helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _myfatoorah_base_url(self):
        self.ensure_one()
        country = self.myfatoorah_country or 'kw'
        mode = 'test' if self.state == 'test' else 'live'
        return MF_ENDPOINTS.get(country, MF_ENDPOINTS['kw'])[mode]

    def _myfatoorah_headers(self):
        self.ensure_one()
        return {
            'Authorization': f'Bearer {self.myfatoorah_api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _mf_request(self, endpoint, payload=None, method='POST', v3_id=None):
        """Central HTTP client for all MyFatoorah API calls."""
        self.ensure_one()
        base = self._myfatoorah_base_url()

        if v3_id is not None:
            url = f'{base}/v3/{endpoint}/{v3_id}'
            method = 'GET'
        else:
            url = f'{base}/v2/{endpoint}'

        try:
            if method == 'GET':
                resp = requests.get(url, headers=self._myfatoorah_headers(), timeout=30)
            else:
                resp = requests.post(
                    url, json=payload, headers=self._myfatoorah_headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            raise ValidationError(_('MyFatoorah: request timed out.'))
        except requests.exceptions.ConnectionError:
            raise ValidationError(_('MyFatoorah: connection error. Check network.'))
        except requests.exceptions.HTTPError as e:
            body = ''
            try:
                body = resp.text
            except Exception:
                pass
            _logger.error('MF HTTP error %s: %s', e, body)
            raise ValidationError(_('MyFatoorah HTTP error: %s\nDetails: %s', str(e), body))

        if not data.get('IsSuccess'):
            msg = data.get('Message') or str(data.get('ValidationErrors', ''))
            _logger.error('MF API [%s] error: %s', endpoint, msg)
            raise ValidationError(_('MyFatoorah: %s', msg))

        return data.get('Data', {})

    # ─────────────────────────────────────────────────────────────────────────
    # Payment API methods
    # ─────────────────────────────────────────────────────────────────────────

    def _mf_initiate_payment(self, amount, currency_code):
        """GET available payment methods — used for connection test."""
        return self._mf_request('InitiatePayment', {
            'InvoiceAmount': round(amount, 3),
            'CurrencyIso': currency_code,
        })

    def _mf_execute_payment(self, tx, token=None):
        """
        Create a hosted payment page via SendPayment.
        Returns dict with InvoiceURL + InvoiceId.
        """
        self.ensure_one()
        base_url = self.get_base_url()
        partner = tx.partner_id

        payload = {
            'CustomerName': partner.name or 'Customer',
            'DisplayCurrencyIso': tx.currency_id.name,
            'MobileCountryCode': '+965',
            'CustomerMobile': self._mf_clean_mobile(partner.phone or ''),
            'CustomerEmail': partner.email or '',
            'InvoiceValue': round(tx.amount, 3),
            'CallBackUrl': f'{base_url}/payment/myfatoorah/return',
            'ErrorUrl': f'{base_url}/payment/myfatoorah/error',
            'Language': 'en',
            'CustomerReference': tx.reference,
            'UserDefinedField': tx.reference,
            'ExpiryDate': '',
            'SaveToken': self.myfatoorah_enable_kfast,
            'NotificationOption': 'LNK',
            'InvoiceItems': self._mf_invoice_items(tx),
        }

        if token:
            payload['Token'] = token

        return self._mf_request('SendPayment', payload)

    def _mf_clean_mobile(self, raw):
        """Strip country code, spaces, non-digits. Max 11 digits (MF limit)."""
        if not raw:
            return ''
        digits = ''.join(c for c in raw if c.isdigit())
        if digits.startswith('965') and len(digits) > 8:
            digits = digits[3:]
        return digits[:11]

    def _mf_invoice_items(self, tx):
        """Build line items from sale order or single-line fallback."""
        items = []
        if hasattr(tx, 'sale_order_ids') and tx.sale_order_ids:
            for line in tx.sale_order_ids[:1].order_line:
                if line.price_subtotal > 0:
                    items.append({
                        'ItemName': (line.product_id.name or line.name or 'Item')[:50],
                        'Quantity': max(1, int(line.product_uom_qty)),
                        'UnitPrice': round(line.price_unit, 3),
                    })
        return items or [{
            'ItemName': tx.reference or 'Payment',
            'Quantity': 1,
            'UnitPrice': round(tx.amount, 3),
        }]

    def _mf_get_payment_status_v3(self, payment_id):
        """GET /v3/payments/{paymentId} — authoritative payment status."""
        return self._mf_request('payments', v3_id=payment_id)

    def _mf_get_payment_status_v2(self, invoice_id):
        """POST /v2/GetPaymentStatus — fallback with InvoiceTransactions list."""
        return self._mf_request('GetPaymentStatus', {
            'Key': str(invoice_id),
            'KeyType': 'InvoiceId',
        })

    def _mf_refund(self, payment_id, amount, reason=''):
        """POST /v2/MakeRefund."""
        return self._mf_request('MakeRefund', {
            'Key': str(payment_id),
            'KeyType': 'PaymentId',
            'RefundChargeOnCustomer': False,
            'ServiceChargeOnCustomer': False,
            'Amount': round(amount, 3),
            'Comment': reason or 'Refund via Odoo',
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Odoo overrides — Community + Enterprise compatible
    # ─────────────────────────────────────────────────────────────────────────

    def _get_supported_currencies(self):
        if self.code != 'myfatoorah':
            return super()._get_supported_currencies()
        return self.env['res.currency'].search([('name', 'in', MF_CURRENCIES)])

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code == 'myfatoorah'):
            # Use hasattr for Enterprise-only fields (safe on Community)
            if hasattr(provider, 'support_tokenization'):
                provider.support_tokenization = provider.myfatoorah_enable_kfast
            if hasattr(provider, 'support_manual_capture'):
                provider.support_manual_capture = False
            if hasattr(provider, 'support_refund'):
                provider.support_refund = 'partial'

    def _get_redirect_form_view(self, is_validation=False):
        if self.code != 'myfatoorah':
            return super()._get_redirect_form_view(is_validation=is_validation)
        return self.env.ref('payment_myfatoorah.redirect_form')

    # ─────────────────────────────────────────────────────────────────────────
    # Cron — poll pending transactions every 15 min
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _mf_cron_sync_pending_transactions(self):
        pending_txs = self.env['payment.transaction'].search([
            ('provider_code', '=', 'myfatoorah'),
            ('state', 'in', ['draft', 'pending']),
            ('myfatoorah_payment_id', '!=', False),
        ])
        _logger.info('MF cron: checking %d pending transaction(s)', len(pending_txs))
        for tx in pending_txs:
            try:
                tx._mf_sync_status()
            except Exception as e:
                _logger.error('MF cron: failed tx %s: %s', tx.reference, str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Backend connection test button
    # ─────────────────────────────────────────────────────────────────────────

    def action_test_myfatoorah_connection(self):
        self.ensure_one()
        if self.code != 'myfatoorah':
            return
        try:
            currency = 'KWD' if self.myfatoorah_country == 'kw' else 'USD'
            self._mf_initiate_payment(1.0, currency)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful ✓'),
                    'message': _('MyFatoorah API token is valid. You are connected.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                },
            }
