# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Wholesale Price',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': "Apply a wholesale price and wholesale taxes on individual POS order lines",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['point_of_sale'],
    'data': [
        'views/product_views.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_wholesale_price/static/src/**/*',
        ],
    },
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
