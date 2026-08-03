# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'National Address Field',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Adds a Saudi National Address field to portal and eCommerce address forms.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['portal', 'website_sale'],
    'data': [
        'views/portal_templates.xml',
        'views/hide_billing_address_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'national_address_field/static/src/scss/national_address.scss',
            'national_address_field/static/src/js/national_address.js',
        ],
    },
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
