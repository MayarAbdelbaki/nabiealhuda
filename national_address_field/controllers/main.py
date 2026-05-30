# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Saving of ``x_national_address`` is handled by whitelisting the field in
# ``res.partner._get_frontend_writable_fields`` (see ``models/res_partner.py``).
# In Odoo 19, both the portal ``/my/account`` form and the eCommerce
# ``/shop/address`` form route their submissions through the shared
# ``CustomerPortal._parse_form_data`` helper, which only persists form keys
# that appear in that whitelist. Because the whitelist override already makes
# the value flow into ``partner.write()`` on both pages, no controller override
# is necessary.
#
# This module is kept as an explicit extension point: subclass the controllers
# below if you later need custom server-side handling (e.g. validating the
# national address format) for the national address field.

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.main import WebsiteSale


class NationalAddressPortal(CustomerPortal):
    """Portal (/my/account) controller — extension point for the national address."""


class NationalAddressWebsiteSale(WebsiteSale):
    """eCommerce (/shop/address) controller — extension point for the national address."""
