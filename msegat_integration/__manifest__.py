# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Msegat SMS OTP & WhatsApp',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': "Verify the phone of new customers with an Msegat SMS code and send invoice PDFs by WhatsApp",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['account', 'phone_validation'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_actions_server_data.xml',
        'views/msegat_otp_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/res_users_views.xml',
        'views/templates.xml',
    ],
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
