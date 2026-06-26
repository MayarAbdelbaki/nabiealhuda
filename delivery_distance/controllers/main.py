# -*- coding: utf-8 -*-
from odoo import _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

# Countries delivery is available to (ISO 3166-1 alpha-2). Keep this in sync
# with ALLOWED_COUNTRY_CODES in static/src/js/checkout_map.js.
ALLOWED_COUNTRY_CODES = {
    "SA",  # Saudi Arabia
    "AE",  # United Arab Emirates
    "KW",  # Kuwait
    "QA",  # Qatar
    "BH",  # Bahrain
    "OM",  # Oman
    "EG",  # Egypt
    "SD",  # Sudan
}


class WebsiteSaleDeliveryCountry(WebsiteSale):
    """Authoritative guard: reject checkout addresses outside the delivery
    area, so a disallowed country cannot be saved even if the client-side
    checks are bypassed.
    """

    def _validate_address_values(self, address_values, *args, **kwargs):
        result = super()._validate_address_values(
            address_values, *args, **kwargs
        )
        country_id = address_values.get('country_id')
        if not country_id:
            return result
        try:
            country = request.env['res.country'].sudo().browse(int(country_id))
        except (TypeError, ValueError):
            return result
        if (
            country.code
            and country.code.upper() not in ALLOWED_COUNTRY_CODES
        ):
            # Odoo returns (invalid_fields, missing_fields, error_messages);
            # the first and third are mutable, so update them in place.
            if isinstance(result, tuple) and len(result) == 3:
                invalid_fields, _missing, error_messages = result
                invalid_fields.add('country_id')
                error_messages.append(
                    _("Delivery is not available to %s.", country.name)
                )
        return result
