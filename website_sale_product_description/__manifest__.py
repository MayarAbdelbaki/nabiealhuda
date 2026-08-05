# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Website Sale Product Description',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Show the product's Sales Description on the eCommerce product page",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['website_sale'],
    'data': [
        'views/product_templates.xml',
    ],
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
