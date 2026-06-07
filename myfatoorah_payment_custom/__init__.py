# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models

import odoo.addons.payment as payment  # prevent circular import error with payment


def post_init_hook(env):
    payment.setup_provider(env, 'myfatoorah')
    # `setup_provider` creates the provider record; link its redirect form view here
    # (it cannot be set in a data file because the record does not exist until now).
    provider = env['payment.provider'].search([('code', '=', 'myfatoorah')], limit=1)
    if provider:
        provider.redirect_form_view_id = env.ref(
            'myfatoorah_payment_custom.myfatoorah_redirect_form'
        )


def uninstall_hook(env):
    payment.reset_payment_provider(env, 'myfatoorah')
