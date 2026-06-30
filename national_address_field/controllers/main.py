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

from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.main import WebsiteSale

# Fields removed from the address forms (see views/portal_templates.xml). They
# must also be dropped from the mandatory set, otherwise both the client-side
# (country_info -> required_fields) and the server-side address validation
# would reject submissions for fields that no longer have an input.
_REMOVED_MANDATORY_FIELDS = {'street', 'zip'}


class NationalAddressPortal(CustomerPortal):
    """Portal (/my/account) controller — drops removed mandatory fields,
    defaults the country to Saudi Arabia, and hides the e-invoicing fields."""

    def _get_mandatory_address_fields(self, country_sudo):
        fields = super()._get_mandatory_address_fields(country_sudo)
        return fields - _REMOVED_MANDATORY_FIELDS

    def _get_default_country(self, *args, **kwargs):
        saudi_arabia = request.env.ref('base.sa', raise_if_not_found=False)
        return saudi_arabia or super()._get_default_country(*args, **kwargs)

    def _prepare_my_account_rendering_values(self, *args, **kwargs):
        """Hide the e-invoicing fields ("Receive invoices" / "Electronic
        format" + helper text) on the /my/account form.

        The ``account`` module renders them only when there is more than one
        invoice sending method and at least one EDI format. Emptying those
        option collections makes their QWeb ``t-if`` conditions render nothing.
        This is done in the controller (not via an XML xpath) because the only
        stable way to target the helper text was by its English wording, which
        breaks view inheritance on translated (e.g. Arabic) pages.
        """
        values = super()._prepare_my_account_rendering_values(*args, **kwargs)
        sending_methods = values.get('invoice_sending_methods')
        if sending_methods:
            # Keep a single method so len() == 1 -> the dropdown is not shown.
            values['invoice_sending_methods'] = dict(list(sending_methods.items())[:1])
        values['invoice_edi_formats'] = {}
        return values


class NationalAddressWebsiteSale(WebsiteSale):
    """eCommerce (/shop/address) controller — drops removed mandatory fields and
    defaults the country to Saudi Arabia."""

    def _get_mandatory_address_fields(self, country_sudo):
        fields = super()._get_mandatory_address_fields(country_sudo)
        return fields - _REMOVED_MANDATORY_FIELDS

    def _get_default_country(self, *args, **kwargs):
        saudi_arabia = request.env.ref('base.sa', raise_if_not_found=False)
        return saudi_arabia or super()._get_default_country(*args, **kwargs)
