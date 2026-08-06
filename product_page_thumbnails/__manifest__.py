# -*- coding: utf-8 -*-
{
    'name': 'Product Page Thumbnails',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Show a row of small image thumbnails under the product name / Add to Cart section',
    'depends': ['website_sale'],
    'data': [
        'data/website_data.xml',
        'views/product_page_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'product_page_thumbnails/static/src/scss/product_page_thumbnails.scss',
            'product_page_thumbnails/static/src/js/product_page_thumbnails.js',
        ],
    },
    'author': 'Mayar',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
