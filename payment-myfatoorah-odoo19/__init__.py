# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import wizard


def post_init_hook(env):
    provider = env.ref(
        'payment_myfatoorah.payment_provider_myfatoorah',
        raise_if_not_found=False,
    )
    if provider:
        provider.write({'state': 'disabled'})


def uninstall_hook(env):
    provider = env.ref(
        'payment_myfatoorah.payment_provider_myfatoorah',
        raise_if_not_found=False,
    )
    if provider:
        provider._remove_payment_methods()
