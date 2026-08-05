# -*- coding: utf-8 -*-
{
    'name': 'Account Reports Language Toggle',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Choose English or Arabic when downloading the Tax Report / Partner Ledger',
    'description': """
Adds a language button to the filter bar of the Tax Report and Partner Ledger
(Accounting > Reporting), letting anyone pick English or Arabic for the
downloaded PDF/XLSX without changing their own account's language.

Also fills in the Arabic (ar_001) translation of the Saudi VAT Return's line
labels (e.g. "1. Standard rated sales"), which Odoo's own l10n_sa module
ships without an Arabic translation at all — otherwise the toggle above
would translate the report's title/headers/framework labels but leave every
actual line label in English.
""",
    'depends': ['account_reports', 'l10n_sa'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'account_reports_language_toggle/static/src/components/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'author': 'Mayar',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
