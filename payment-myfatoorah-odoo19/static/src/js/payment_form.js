/** @odoo-module **/
/**
 * MyFatoorah Payment Form — Full Edition
 * Handles the redirect to MyFatoorah hosted payment page.
 * For token-based (subscription) charges, the charge already happened
 * server-side so we skip the redirect.
 */

import { PaymentForm } from '@payment/js/payment_form';
import { patch } from '@web/core/utils/patch';

patch(PaymentForm.prototype, {
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'myfatoorah') {
            return super._processRedirectFlow(...arguments);
        }

        // Token charge — already processed server-side, just go to status page
        if (processingValues.is_token_charge) {
            window.location.href = '/payment/status';
            return;
        }

        const redirectUrl = processingValues.api_url;
        if (redirectUrl) {
            window.location.href = redirectUrl;
        } else {
            this._displayError(
                'MyFatoorah Error',
                'No payment URL returned. Please try again or contact support.',
            );
        }
    },
});
