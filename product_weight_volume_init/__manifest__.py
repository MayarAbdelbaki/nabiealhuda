# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Product Weight & Volume Init',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': "One-time import of product Weight (KG) and Volume (m^3) from spreadsheet via raw SQL.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['product'],
    # NB: the data is applied with raw SQL in post_init_hook, NOT as ir.model.data
    # records. That is intentional: uninstalling this module will NOT revert the
    # weight/volume values written to existing product templates.
    'data': [],
    'post_init_hook': 'post_init_hook',
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
