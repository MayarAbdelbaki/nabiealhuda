import logging
import pprint

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_processing_values(self, processing_values):
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'myfatoorah':
            return res

        provider = self.provider_id
        base_url = provider.get_base_url()

        return_url = url_join(base_url, '/payment/myfatoorah/return')
        error_url = url_join(base_url, '/payment/myfatoorah/error')
        webhook_url = url_join(base_url, '/payment/myfatoorah/webhook')

        lang = 'ar' if self.partner_lang and 'ar' in self.partner_lang else 'en'

        invoice_items = [{
            'ItemName': self.reference or 'Payment',
            'Quantity': 1,
            'UnitPrice': round(self.amount, 2),
        }]

        payload = {
            'InvoiceValue': round(self.amount, 2),
            'CustomerName': self.partner_name or self.partner_id.name or 'Customer',
            'NotificationOption': 'LNK',
            'CallBackUrl': return_url,
            'ErrorUrl': error_url,
            'Language': lang,
            'DisplayCurrencyIso': self.currency_id.name if self.currency_id else 'SAR',
            'CustomerReference': self.reference,
            'InvoiceItems': invoice_items,
        }

        if self.partner_email:
            payload['CustomerEmail'] = self.partner_email
            payload['NotificationOption'] = 'ALL'

        if self.partner_phone:
            phone = ''.join(c for c in self.partner_phone if c.isdigit())
            if phone:
                phone = phone[-11:]
                payload['CustomerMobile'] = phone

        partner = self.partner_id
        if partner and partner.street:
            payload['CustomerAddress'] = {
                'Block': '',
                'Street': partner.street or '',
                'HouseBuildingNo': '',
                'Address': ', '.join(filter(None, [
                    partner.street, partner.street2,
                    partner.city,
                    partner.state_id.name if partner.state_id else '',
                    partner.zip,
                ])),
                'AddressInstructions': '',
            }

        if provider.myfatoorah_webhook_enabled:
            payload['WebhookUrl'] = webhook_url

        _logger.info(
            "MyFatoorah: Creating invoice for transaction %s (amount: %s %s)",
            self.reference, self.amount, self.currency_id.name,
        )

        response_data = provider._myfatoorah_make_request('/v2/SendPayment', payload)

        invoice_url = response_data.get('InvoiceURL')
        invoice_id = response_data.get('InvoiceId')

        if not invoice_url:
            raise ValidationError(_("MyFatoorah: No invoice URL received."))

        _logger.info(
            "MyFatoorah: Invoice created — ID: %s, URL: %s, Reference: %s",
            invoice_id, invoice_url, self.reference,
        )

        self.provider_reference = str(invoice_id) if invoice_id else ''

        return {
            'api_url': invoice_url,
            'reference': self.reference,
        }

    def _get_specific_rendering_values(self, processing_values):
        if self.provider_code != 'myfatoorah':
            return super()._get_specific_rendering_values(processing_values)

        invoice_url = processing_values.get('api_url') or processing_values.get('invoice_url')
        if not invoice_url:
            raise ValidationError(_("MyFatoorah: Missing invoice URL for redirect."))

        _logger.info("MyFatoorah: Rendering redirect to %s for tx %s", invoice_url, self.reference)
        return {'api_url': invoice_url}

    @api.model
    def _get_tx_from_payment_data(self, provider_code, payment_data):
        if provider_code != 'myfatoorah':
            return super()._get_tx_from_payment_data(provider_code, payment_data)

        reference = payment_data.get('CustomerReference')
        payment_id = payment_data.get('paymentId')
        invoice_id = payment_data.get('InvoiceId')

        if reference:
            tx = self.search([('reference', '=', reference), ('provider_code', '=', 'myfatoorah')], limit=1)
            if tx:
                return tx

        if invoice_id:
            tx = self.search([('provider_reference', '=', str(invoice_id)), ('provider_code', '=', 'myfatoorah')], limit=1)
            if tx:
                return tx

        if payment_id:
            providers = self.env['payment.provider'].sudo().search([
                ('code', '=', 'myfatoorah'),
                ('state', 'in', ['enabled', 'test']),
            ])
            for provider in providers:
                try:
                    status_data = provider._myfatoorah_make_request(
                        '/v2/GetPaymentStatus',
                        {'Key': payment_id, 'KeyType': 'PaymentId'},
                    )
                    ref = status_data.get('CustomerReference')
                    inv_id = status_data.get('InvoiceId')
                    if ref:
                        tx = self.search([('reference', '=', ref), ('provider_code', '=', 'myfatoorah')], limit=1)
                        if tx:
                            return tx
                    if inv_id:
                        tx = self.search([('provider_reference', '=', str(inv_id)), ('provider_code', '=', 'myfatoorah')], limit=1)
                        if tx:
                            return tx
                except Exception as e:
                    _logger.warning("MyFatoorah: Error querying payment status: %s", str(e))
                    continue

        raise ValidationError(_("MyFatoorah: No transaction found for notification data."))

    def _process(self, provider_code, payment_data):
        if self.provider_code != 'myfatoorah':
            return super()._process(provider_code, payment_data)

        payment_id = payment_data.get('paymentId')
        invoice_id = payment_data.get('InvoiceId') or self.provider_reference

        if payment_id:
            key, key_type = payment_id, 'PaymentId'
        elif invoice_id:
            key, key_type = invoice_id, 'InvoiceId'
        else:
            self._set_error(_("MyFatoorah: Missing payment identification."))
            return

        try:
            status_data = self.provider_id._myfatoorah_make_request(
                '/v2/GetPaymentStatus',
                {'Key': str(key), 'KeyType': key_type},
            )
        except ValidationError:
            self._set_error(_("MyFatoorah: Failed to verify payment status."))
            return

        _logger.info(
            "MyFatoorah: Payment status for tx %s:\n%s",
            self.reference, pprint.pformat(status_data),
        )

        invoice_status = status_data.get('InvoiceStatus', '').lower()
        invoice_id_resp = status_data.get('InvoiceId')
        if invoice_id_resp and not self.provider_reference:
            self.provider_reference = str(invoice_id_resp)

        transactions = status_data.get('InvoiceTransactions', [])
        latest_tx = transactions[-1] if transactions else None
        tx_status = latest_tx.get('TransactionStatus', '').lower() if latest_tx else invoice_status

        _logger.info(
            "MyFatoorah: tx %s — invoice_status: %s, tx_status: %s",
            self.reference, invoice_status, tx_status,
        )

        if invoice_status == 'paid' or tx_status in ('success', 'succss'):
            self._set_done()
        elif invoice_status in ('pending', 'initiated') or tx_status in ('pending', 'initiated'):
            self._set_pending()
        elif invoice_status in ('expired', 'canceled') or tx_status in ('expired', 'canceled'):
            self._set_canceled(state_message=_("MyFatoorah: Payment was %s.") % (invoice_status or tx_status))
        elif invoice_status == 'failed' or tx_status == 'failed':
            error_msg = (latest_tx.get('Error', '') or latest_tx.get('ErrorCode', '')) if latest_tx else ''
            self._set_error(_("MyFatoorah: Payment failed. %s") % error_msg)
        else:
            self._set_error(_("MyFatoorah: Unknown payment status: %s") % (invoice_status or tx_status or 'unknown'))