# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: MyFatoorah — Full Edition',
    'version': '19.0.3.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'MyFatoorah — Complete GCC Payment Gateway for Odoo 19 (Community & Enterprise)',
    'description': """
MyFatoorah Full Edition — Odoo 19
===================================
The most complete MyFatoorah integration for Odoo 19.
Compatible with Odoo Community and Enterprise editions.

PAYMENT TOUCHPOINTS (100%):
  ✅ eCommerce checkout (Website + Shop)
  ✅ Customer portal — pay invoices online
  ✅ Sales order online payment
  ✅ Payment links (send to customer via email/WhatsApp)
  ✅ Down payments on sales orders
  ✅ Subscriptions + recurring billing (KFast tokenization)

PAYMENT METHODS (GCC):
  ✅ KNET (Kuwait)
  ✅ Visa / Mastercard
  ✅ Apple Pay
  ✅ Google Pay
  ✅ STC Pay
  ✅ Mada (Saudi Arabia)
  ✅ Benefit (Bahrain)
  ✅ AMEX
  ✅ UAE Debit Cards

PAYMENT LIFECYCLE:
  ✅ SendPayment hosted page — customer picks payment method
  ✅ v3 API status validation (authoritative)
  ✅ v2 fallback with InvoiceTransactions failure detection
  ✅ Auto-confirm: sales order → confirmed on payment
  ✅ Auto-post: invoice → paid on payment
  ✅ Failed/cancelled → immediate cancellation with error message
  ✅ Scheduled cron — polls pending transactions every 15 min
  ✅ Full + partial refunds from Odoo backend
  ✅ Webhook v2 with HMAC-SHA256 signature verification
  ✅ Card brand + last 4 digits captured per transaction
  ✅ KFast tokenization for saved cards (subscriptions)

MULTI-COUNTRY (GCC + MENA):
  ✅ Kuwait, Saudi Arabia, UAE, Bahrain, Qatar, Oman, Jordan, Egypt

COMPATIBILITY:
  ✅ Odoo 19 Community Edition
  ✅ Odoo 19 Enterprise Edition
  ✅ Self-hosted (Docker, Coolify, bare metal)
  ✅ Odoo.sh

Developed by Netofy — Kuwait | netofy.com
    """,
    'author': 'Netofy',
    'website': 'https://netofy.com',
    'license': 'LGPL-3',
    'depends': [
        'payment',       # Core payment framework — required
        'account',       # Invoices, journals, reconciliation — required
        'sale_management',  # Sales orders auto-confirm — required for eCommerce
        'website_sale',  # eCommerce checkout flow — required for online shop
        'mail',          # Receipt emails — required
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/myfatoorah_refund_wizard_views.xml',
        'wizard/myfatoorah_sync_wizard_views.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_token_views.xml',
        'views/payment_myfatoorah_templates.xml',
        'data/payment_provider_data.xml',
        'data/payment_method_data.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_myfatoorah/static/src/js/payment_form.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
