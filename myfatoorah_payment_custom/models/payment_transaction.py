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

    # === NOTIFICATION / STATUS HANDLING (Odoo 19 API) === #

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """ Override of `payment` to extract the reference from MyFatoorah data.

        MyFatoorah's redirect only carries `paymentId`. We resolve it to our
        transaction reference via the GetPaymentStatus API (it returns
        `CustomerReference`, which we set to `self.reference` when creating the
        invoice). We also accept a direct `CustomerReference`/`InvoiceId` from
        webhooks.
        """
        if provider_code != 'myfatoorah':
            return super()._extract_reference(provider_code, payment_data)

        # 1. Direct reference (webhook or stored on payment_data).
        reference = payment_data.get('CustomerReference') or payment_data.get('reference')
        if reference:
            return reference

        # 2. Resolve via InvoiceId stored as provider_reference.
        invoice_id = payment_data.get('InvoiceId')
        if invoice_id:
            tx = self.search([
                ('provider_reference', '=', str(invoice_id)),
                ('provider_code', '=', 'myfatoorah'),
            ], limit=1)
            if tx:
                return tx.reference

        # 3. Resolve a bare paymentId by asking MyFatoorah for the status.
        payment_id = payment_data.get('paymentId')
        if payment_id:
            providers = self.env['payment.provider'].sudo().search([
                ('code', '=', 'myfatoorah'),
                ('state', 'in', ['enabled', 'test']),
            ])
            for provider in providers:
                try:
                    status_data = provider._myfatoorah_make_request(
                        '/v2/GetPaymentStatus',
                        {'Key': str(payment_id), 'KeyType': 'PaymentId'},
                    )
                except Exception as e:  # noqa: BLE001 - try the next provider
                    _logger.warning("MyFatoorah: status lookup failed: %s", str(e))
                    continue
                # Cache the status data so _apply_updates doesn't re-fetch it.
                payment_data['_myfatoorah_status'] = status_data
                ref = status_data.get('CustomerReference')
                if ref:
                    return ref
                inv_id = status_data.get('InvoiceId')
                if inv_id:
                    tx = self.search([
                        ('provider_reference', '=', str(inv_id)),
                        ('provider_code', '=', 'myfatoorah'),
                    ], limit=1)
                    if tx:
                        return tx.reference

        _logger.warning(
            "MyFatoorah: could not extract a reference from payment data: %s", payment_data
        )
        return None

    def _extract_amount_data(self, payment_data):
        """ Override of `payment`: skip amount validation for MyFatoorah.

        MyFatoorah is a redirect gateway; the authoritative amount is the one we
        sent. Returning `None` tells the core to skip the amount/currency check.
        """
        if self.provider_code != 'myfatoorah':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        """ Override of `payment` to set the MyFatoorah transaction state.

        Calls GetPaymentStatus to get the definitive status and maps it to the
        Odoo transaction state. Note: `self.ensure_one()` is guaranteed by
        `_process`.
        """
        if self.provider_code != 'myfatoorah':
            return super()._apply_updates(payment_data)

        # Reuse status data fetched during _extract_reference if available.
        status_data = payment_data.get('_myfatoorah_status')
        if not status_data:
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

        invoice_status = (status_data.get('InvoiceStatus') or '').lower()
        invoice_id_resp = status_data.get('InvoiceId')
        if invoice_id_resp and not self.provider_reference:
            self.provider_reference = str(invoice_id_resp)

        transactions = status_data.get('InvoiceTransactions', [])
        latest_tx = transactions[-1] if transactions else None
        tx_status = (latest_tx.get('TransactionStatus') or '').lower() if latest_tx else invoice_status

        _logger.info(
            "MyFatoorah: tx %s — invoice_status: %s, tx_status: %s",
            self.reference, invoice_status, tx_status,
        )

        # Success: invoice is paid, or the latest transaction succeeded.
        # The `sale` module auto-confirms the linked order(s) when the tx is done.
        if invoice_status == 'paid' or tx_status in ('success', 'succss'):
            self._set_done()
        # Failure takes priority over the invoice's "pending" — a failed attempt
        # leaves the invoice unpaid (pending) but the payment did NOT go through.
        elif tx_status == 'failed' or invoice_status == 'failed':
            error_msg = (latest_tx.get('Error', '') or latest_tx.get('ErrorCode', '')) if latest_tx else ''
            self._set_error(_("MyFatoorah: Payment failed. %s") % (error_msg or _("The payment was declined.")))
            self._myfatoorah_cancel_orders_if_no_retry()
        elif invoice_status in ('expired', 'canceled') or tx_status in ('expired', 'canceled'):
            self._set_canceled(state_message=_("MyFatoorah: Payment was %s.") % (invoice_status or tx_status))
            self._myfatoorah_cancel_orders_if_no_retry()
        # Genuinely still in progress: no failed attempt yet, invoice unpaid.
        elif invoice_status in ('pending', 'initiated') or tx_status in ('pending', 'initiated'):
            self._set_pending()
        else:
            self._set_error(_("MyFatoorah: Unknown payment status: %s") % (invoice_status or tx_status or 'unknown'))

    def _myfatoorah_cancel_orders_if_no_retry(self):
        """Cancel the linked sale order(s) after a failed/declined payment.

        To avoid cancelling an order the customer is still paying, we only cancel
        when there is NO other transaction for the same order still in a
        non-final state (draft/pending/authorized). This lets customers retry; we
        only cancel once they have truly failed with no pending attempt left.
        """
        self.ensure_one()
        orders = self.sale_order_ids.filtered(lambda o: o.state in ('draft', 'sent'))
        for order in orders:
            # Other live transactions for this order (excluding the current one).
            pending_txs = order.transaction_ids.filtered(
                lambda t: t.id != self.id and t.state in ('draft', 'pending', 'authorized')
            )
            if pending_txs:
                _logger.info(
                    "MyFatoorah: Order %s NOT cancelled — %s pending transaction(s) remain.",
                    order.name, len(pending_txs),
                )
                continue
            try:
                order._action_cancel()
                _logger.info(
                    "MyFatoorah: Order %s cancelled after failed payment (tx %s).",
                    order.name, self.reference,
                )
            except Exception as e:  # noqa: BLE001 - never break the payment flow on cancel
                _logger.warning(
                    "MyFatoorah: Could not cancel order %s: %s", order.name, str(e),
                )