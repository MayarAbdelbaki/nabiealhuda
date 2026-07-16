# -*- coding: utf-8 -*-
{
    'name': 'Daily Sales Report',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Scheduled POS, Sales and eCommerce reports emailed as XLSX attachments',
    'description': """
Daily Sales Report
===================

Configure one or more report profiles that automatically gather POS orders,
Sales orders and eCommerce orders for a daily/weekly/monthly period, build an
XLSX file per report type, and email them to a list of recipients. Every send
attempt (successful or failed) is logged in a read-only history log.
""",
    'author': 'Mayar',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'sale_management', 'website_sale', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/report_config_views.xml',
        'views/report_history_views.xml',
        'views/menu_views.xml',
        'data/ir_cron.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
