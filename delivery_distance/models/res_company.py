# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    partner_latitude = fields.Float(
        related='partner_id.partner_latitude',
        string='Geo Latitude',
        readonly=False,
        digits=(10, 7),
    )
    partner_longitude = fields.Float(
        related='partner_id.partner_longitude',
        string='Geo Longitude',
        readonly=False,
        digits=(10, 7),
    )

    def action_geo_localize_company(self):
        """Fill the company coordinates from its address.

        Uses the ``base_geolocalize`` provider configured in Settings
        (OpenStreetMap/Nominatim works for free, no API key required).
        """
        for company in self:
            partner = company.partner_id
            if not partner:
                raise UserError(
                    _("This company has no contact address to locate.")
                )
            try:
                partner.geo_localize()
            except Exception as exc:  # noqa: BLE001
                _logger.error(
                    "Company geo-localization failed for %s: %s",
                    company.name, exc,
                )
                raise UserError(_(
                    "Could not locate the company address. Please check the "
                    "address and the geolocation provider in Settings."
                ))
            if not (partner.partner_latitude and partner.partner_longitude):
                raise UserError(_(
                    "The geolocation provider returned no coordinates for "
                    "this address. Please refine the address and try again."
                ))
        return True
