# -*- coding: utf-8 -*-
{
    'name': 'Invoice Company/Customer Position Swap',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'On invoices and sale orders, show company and customer on the same header line',
    'description': """
The company's chosen report theme ("Bubble") normally shows only the
company's own address in the header, with the printed document's recipient
appearing separately, further down the page. For invoices and sale orders
(quotations/orders, including eCommerce orders) specifically, show both on
the same header line instead: company on the left, customer (billing, plus
shipping when it differs) on the right. Every other document keeps the
theme's normal arrangement.
""",
    'depends': ['account', 'sale'],
    'data': [
        'views/report_layout_bubble.xml',
    ],
    'author': 'Mayar',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
