# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # === ACTION METHODS === #

    def _get_specific_processing_values(self, processing_values):
        """ Override of `payment` to return MyFatoorah-specific processing values.

        Calls the MyFatoorah SendPayment API to create an invoice
        and returns the invoice URL for customer redirect.

        Note: self.ensure_one() from `_get_processing_values`.

        :param dict processing_values: The generic processing values of the transaction.
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'myfatoorah':
            return res

        provider = self.provider_id
        base_url = provider.get_base_url()

        # Build callback URLs
        return_url = url_join(base_url, '/payment/myfatoorah/return')
        error_url = url_join(base_url, '/payment/myfatoorah/error')
        webhook_url = url_join(base_url, '/payment/myfatoorah/webhook')

        # Determine language
        lang = 'ar' if self.partner_lang and 'ar' in self.partner_lang else 'en'

        # Build invoice items from sale order lines if available.
        # MyFatoorah requires sum(Quantity * UnitPrice) == InvoiceValue, so we
        # use the line subtotal (incl. tax & discount) as a single-quantity item
        # and verify the total matches the transaction amount.
        invoice_value = round(self.amount, 3)
        invoice_items = []
        if self.sale_order_ids:
            for order in self.sale_order_ids:
                for line in order.order_line:
                    line_total = round(line.price_total, 3)
                    if line.product_id and line_total > 0:
                        invoice_items.append({
                            'ItemName': (line.product_id.name or line.name or 'Product')[:75],
                            'Quantity': 1,
                            'UnitPrice': line_total,
                        })

        # Verify items sum matches the invoice value; if not, fall back to a
        # single line equal to the amount to avoid MyFatoorah's
        # "Invoice total value must be the same total items value" error.
        items_total = round(sum(i['Quantity'] * i['UnitPrice'] for i in invoice_items), 3)
        if not invoice_items or items_total != invoice_value:
            invoice_items = [{
                'ItemName': (self.reference or 'Payment')[:75],
                'Quantity': 1,
                'UnitPrice': invoice_value,
            }]

        # Build the SendPayment payload
        payload = {
            'InvoiceValue': invoice_value,
            'CustomerName': self.partner_name or self.partner_id.name or 'Customer',
            'NotificationOption': 'LNK',
            'CallBackUrl': return_url,
            'ErrorUrl': error_url,
            'Language': lang,
            'DisplayCurrencyIso': self.currency_id.name if self.currency_id else 'SAR',
            'CustomerReference': self.reference,
            'InvoiceItems': invoice_items,
        }

        # Add optional customer data
        if self.partner_email:
            payload['CustomerEmail'] = self.partner_email
            payload['NotificationOption'] = 'ALL'

        if self.partner_phone:
            # MyFatoorah expects CustomerMobile as digits only, max 11 chars,
            # without the country code (that goes in MobileCountryCode).
            digits = ''.join(c for c in self.partner_phone if c.isdigit())
            # Strip a leading country code, e.g. Saudi '966' / Kuwait '965' / Egypt '20'.
            for cc in ('966', '965', '968', '973', '974', '971', '20'):
                if digits.startswith(cc) and len(digits) - len(cc) >= 7:
                    digits = digits[len(cc):]
                    break
            # Strip a leading trunk '0' if present (e.g. 0543934560 -> 543934560).
            digits = digits.lstrip('0')
            phone = digits[:11]
            if phone:
                payload['CustomerMobile'] = phone
                payload['MobileCountryCode'] = '+966'
                if payload['NotificationOption'] == 'LNK':
                    payload['NotificationOption'] = 'SMS'

        # Add customer address if available
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

        # Add webhook URL if enabled
        if provider.myfatoorah_webhook_enabled:
            payload['WebhookUrl'] = webhook_url

        _logger.info(
            "MyFatoorah: Creating invoice for transaction %s (amount: %s %s)",
            self.reference, self.amount, self.currency_id.name,
        )

        # Call SendPayment API
        response_data = provider._myfatoorah_make_request('/v2/SendPayment', payload)

        invoice_url = response_data.get('InvoiceURL')
        invoice_id = response_data.get('InvoiceId')

        if not invoice_url:
            raise ValidationError(_(
                "MyFatoorah: No invoice URL received from the payment gateway."
            ))

        _logger.info(
            "MyFatoorah: Invoice created — ID: %s, URL: %s, Reference: %s",
            invoice_id, invoice_url, self.reference,
        )

        # Store the invoice ID as provider_reference for later lookup
        self.provider_reference = str(invoice_id) if invoice_id else ''

        return {
            'api_url': invoice_url,
            'reference': self.reference,
        }

    # === NOTIFICATION HANDLING === #

    def _search_by_reference(self, provider_code, payment_data):
        """ Override of `payment` to find the transaction based on MyFatoorah data.

        :param str provider_code: The provider code.
        :param dict payment_data: The payment data from callback/webhook.
        :return: The matching transaction.
        :rtype: payment.transaction recordset
        :raises ValidationError: If the transaction cannot be found.
        """
        if provider_code != 'myfatoorah':
            return super()._search_by_reference(provider_code, payment_data)

        tx = self.env['payment.transaction']

        reference = payment_data.get('CustomerReference')
        payment_id = payment_data.get('paymentId')
        invoice_id = payment_data.get('InvoiceId')

        _logger.info(
            "MyFatoorah: Looking up transaction — reference: %s, paymentId: %s, invoiceId: %s",
            reference, payment_id, invoice_id,
        )

        # Try finding by reference first
        if reference:
            tx = self.search([
                ('reference', '=', reference),
                ('provider_code', '=', 'myfatoorah'),
            ], limit=1)
            if tx:
                return tx

        # Try finding by provider_reference (InvoiceId)
        if invoice_id:
            tx = self.search([
                ('provider_reference', '=', str(invoice_id)),
                ('provider_code', '=', 'myfatoorah'),
            ], limit=1)
            if tx:
                return tx

        # If we have a paymentId, query MyFatoorah API for details
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
                        tx = self.search([
                            ('reference', '=', ref),
                            ('provider_code', '=', 'myfatoorah'),
                        ], limit=1)
                        if tx:
                            return tx
                    if inv_id:
                        tx = self.search([
                            ('provider_reference', '=', str(inv_id)),
                            ('provider_code', '=', 'myfatoorah'),
                        ], limit=1)
                        if tx:
                            return tx
                except Exception as e:
                    _logger.warning(
                        "MyFatoorah: Error querying payment status for lookup: %s", str(e),
                    )
                    continue

        raise ValidationError(_(
            "MyFatoorah: No transaction found matching the notification data "
            "(reference: %(ref)s, paymentId: %(pid)s, invoiceId: %(iid)s).",
            ref=reference, pid=payment_id, iid=invoice_id,
        ))

    def _apply_updates(self, payment_data):
        """ Override of `payment` to update the transaction from MyFatoorah data.

        Calls GetPaymentStatus to get the definitive payment status.

        Note: `self.ensure_one()` from the base implementation.

        :param dict payment_data: The payment data from callback/webhook.
        :return: None
        """
        super()._apply_updates(payment_data)
        if self.provider_code != 'myfatoorah':
            return

        payment_id = payment_data.get('paymentId')
        invoice_id = payment_data.get('InvoiceId') or self.provider_reference

        _logger.info(
            "MyFatoorah: Processing notification for tx %s (paymentId: %s, invoiceId: %s)",
            self.reference, payment_id, invoice_id,
        )

        # Determine the key for GetPaymentStatus
        if payment_id:
            key = payment_id
            key_type = 'PaymentId'
        elif invoice_id:
            key = invoice_id
            key_type = 'InvoiceId'
        else:
            _logger.error(
                "MyFatoorah: No paymentId or invoiceId in notification for tx %s",
                self.reference,
            )
            self._set_error(_(
                "MyFatoorah: Missing payment identification in the notification."
            ))
            return

        # Call GetPaymentStatus
        try:
            status_data = self.provider_id._myfatoorah_make_request(
                '/v2/GetPaymentStatus',
                {'Key': str(key), 'KeyType': key_type},
            )
        except ValidationError as e:
            _logger.error(
                "MyFatoorah: Error getting payment status for tx %s: %s",
                self.reference, str(e),
            )
            self._set_error(_(
                "MyFatoorah: Failed to verify payment status."
            ))
            return

        _logger.info(
            "MyFatoorah: Payment status response for tx %s:\n%s",
            self.reference, pprint.pformat(status_data),
        )

        # Extract status
        invoice_status = status_data.get('InvoiceStatus', '').lower()
        invoice_id_resp = status_data.get('InvoiceId')

        if invoice_id_resp and not self.provider_reference:
            self.provider_reference = str(invoice_id_resp)

        # Get the latest transaction from InvoiceTransactions
        transactions = status_data.get('InvoiceTransactions', [])
        latest_tx = None
        if transactions:
            latest_tx = transactions[-1]
            tx_status = latest_tx.get('TransactionStatus', '').lower()
        else:
            tx_status = invoice_status

        _logger.info(
            "MyFatoorah: Transaction %s — invoice_status: %s, tx_status: %s",
            self.reference, invoice_status, tx_status,
        )

        # Map MyFatoorah statuses to Odoo states
        if invoice_status == 'paid' or tx_status in ('success', 'succss'):
            self._set_done()
        elif invoice_status in ('pending', 'initiated') or tx_status in ('pending', 'initiated'):
            self._set_pending()
        elif invoice_status in ('expired', 'canceled') or tx_status in ('expired', 'canceled'):
            self._set_canceled(state_message=_(
                "MyFatoorah: Payment was %(status)s.",
                status=invoice_status or tx_status,
            ))
        elif invoice_status == 'failed' or tx_status == 'failed':
            error_msg = ''
            if latest_tx:
                error_msg = latest_tx.get('Error', '') or latest_tx.get('ErrorCode', '')
            self._set_error(_(
                "MyFatoorah: Payment failed. %(error)s",
                error=error_msg,
            ))
        else:
            _logger.warning(
                "MyFatoorah: Unknown payment status for tx %s: invoice=%s, tx=%s",
                self.reference, invoice_status, tx_status,
            )
            self._set_error(_(
                "MyFatoorah: Received unknown payment status: %(status)s",
                status=invoice_status or tx_status or 'unknown',
            ))
