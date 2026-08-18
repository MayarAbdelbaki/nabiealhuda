# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Sale Order Line Product Prices',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': "Show the product's saved sales price and cost as read-only reference columns on sale order lines",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['sale_management'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
