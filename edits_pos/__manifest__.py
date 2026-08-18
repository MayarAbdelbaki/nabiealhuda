
{
    'name': 'POS Receipt Edits',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': "Point of Sale tweaks: customised receipt, and wider product tiles that show the full product name.",
    'description': " ",
    'depends': ['point_of_sale', 'l10n_sa_pos'],
    'assets': {
        'point_of_sale._assets_pos': [
            'edits_pos/static/src/overrides/order_receipt.xml',
            'edits_pos/static/src/overrides/pos_receipt.css',
            'edits_pos/static/src/overrides/receipt_filename.js',
            'edits_pos/static/src/overrides/receipt_page_size.js',
            'edits_pos/static/src/overrides/pos_product_card.css',
        ],
    },
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
