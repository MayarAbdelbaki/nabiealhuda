# -*- coding: utf-8 -*-
import logging
from math import ceil

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# OSRM routing (free, no API key) returns the driving distance between two
# coordinates. Nominatim geocodes an address to coordinates when a partner has
# none stored. Both are public OpenStreetMap services.
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT = 15


class DeliveryDistanceRule(models.Model):
    _name = 'delivery.distance.rule'
    _description = 'Distance Based Delivery Pricing Rule'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Delivery Method',
        required=True,
        ondelete='cascade',
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        required=True,
        help="Destination country this pricing rule applies to.",
    )
    block_km = fields.Float(
        string='Block (km)',
        default=18.0,
        help="Distance covered by one charge block, in kilometers.",
    )
    price_per_block = fields.Float(
        string='Price per Block',
        default=25.0,
        help="Price charged for each started block.",
    )
    max_distance_km = fields.Float(
        string='Max Distance (km)',
        default=0.0,
        help="Optional upper distance limit for this rule. 0 means no limit. "
             "Multiple rows for the same country build distance tiers.",
    )


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('distance_based', 'Based on Distance')],
        ondelete={'distance_based': 'set default'},
    )
    rule_ids = fields.One2many(
        'delivery.distance.rule',
        'carrier_id',
        string='Distance Pricing Rules',
        copy=True,
    )
    distance_origin_partner_id = fields.Many2one(
        'res.partner',
        string='Origin Address',
        help="Address used as the origin for distance computation. "
             "If empty, the warehouse address (or the company address) is used.",
    )
    osrm_base_url = fields.Char(
        string='OSRM Server URL',
        help="Base URL of the OSRM routing service used to compute the road "
             "distance (free, no API key). Leave empty to use the public "
             "demo server https://router.project-osrm.org.",
    )
    distance_fallback_price = fields.Float(
        string='Fallback Price',
        help="Price returned when the distance cannot be computed, no rule "
             "matches, or the destination country is not configured. "
             "If 0, the checkout shows an error instead.",
    )

    @api.onchange('delivery_type')
    def _onchange_delivery_type_distance(self):
        """Apply sensible defaults when picking the distance provider.

        The distance method only computes a rate locally (no real carrier),
        so billing should use the estimated cost and no shipment is created.
        """
        if self.delivery_type == 'distance_based':
            self.integration_level = 'rate'
            self.invoice_policy = 'estimated'

    @api.model
    def _distance_apply_defaults(self, vals):
        """Force distance-provider defaults unless explicitly overridden."""
        if vals.get('delivery_type') == 'distance_based':
            vals.setdefault('integration_level', 'rate')
            vals.setdefault('invoice_policy', 'estimated')
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._distance_apply_defaults(vals)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('delivery_type') == 'distance_based':
            self._distance_apply_defaults(vals)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Origin / destination resolution
    # ------------------------------------------------------------------
    def _distance_get_origin_partner(self, order):
        """Resolve the origin address used for distance computation."""
        self.ensure_one()
        if self.distance_origin_partner_id:
            return self.distance_origin_partner_id
        if order.warehouse_id and order.warehouse_id.partner_id:
            return order.warehouse_id.partner_id
        return order.company_id.partner_id

    def _distance_default_origin_partner(self):
        """Origin to use when there is no sale order to read a warehouse from.

        Callers outside the sale flow (the Point of Sale, for one) have no
        ``warehouse_id``; they either pass their own origin to
        :meth:`_distance_rate_for_partner` or fall back to this.
        """
        self.ensure_one()
        if self.distance_origin_partner_id:
            return self.distance_origin_partner_id
        return self.company_id.partner_id or self.env.company.partner_id

    def _distance_partner_coords(self, partner):
        """Return ``(latitude, longitude)`` for a partner, or False.

        Prefer the stored geocoded coordinates; geocode via ``geo_localize``
        if missing; finally fall back to a Nominatim address lookup. OSRM needs
        real coordinates, so an address string alone is not enough.
        """
        if not partner:
            return False
        if not (partner.partner_latitude and partner.partner_longitude):
            try:
                partner.geo_localize()
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Distance delivery: geo_localize failed for partner %s: %s",
                    partner.id, exc,
                )
        if partner.partner_latitude and partner.partner_longitude:
            return (partner.partner_latitude, partner.partner_longitude)
        return self._distance_geocode_address(partner)

    def _distance_geocode_address(self, partner):
        """Geocode a partner's textual address to coordinates via Nominatim."""
        parts = [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name if partner.state_id else None,
            partner.zip,
            partner.country_id.name if partner.country_id else None,
        ]
        address = ", ".join(p for p in parts if p)
        if not address:
            return False
        try:
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params={'format': 'jsonv2', 'limit': 1, 'q': address},
                headers={'User-Agent': 'Odoo-delivery_distance'},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            _logger.error(
                "Distance delivery: Nominatim geocoding failed: %s", exc,
            )
            return False
        if not data:
            _logger.warning(
                "Distance delivery: no Nominatim result for '%s'.", address,
            )
            return False
        try:
            return (float(data[0]['lat']), float(data[0]['lon']))
        except (KeyError, ValueError, IndexError):
            _logger.error(
                "Distance delivery: unexpected Nominatim payload: %s", data,
            )
            return False

    def _distance_compute_km(self, origin_partner, dest_partner):
        """Return the driving distance in km via OSRM.

        Returns a float (km) on success or False on failure.
        """
        self.ensure_one()
        origin = self._distance_partner_coords(origin_partner)
        destination = self._distance_partner_coords(dest_partner)
        if not origin or not destination:
            _logger.warning(
                "Distance delivery: missing origin (%s) or destination (%s) "
                "coordinates.", origin, destination,
            )
            return False

        base_url = (self.osrm_base_url or '').strip().rstrip('/')
        if base_url:
            route_url = base_url + '/route/v1/driving/'
        else:
            route_url = OSRM_ROUTE_URL
        # OSRM expects "lon,lat;lon,lat" (longitude first).
        coords = "%s,%s;%s,%s" % (
            origin[1], origin[0], destination[1], destination[0],
        )
        try:
            response = requests.get(
                route_url + coords,
                params={'overview': 'false'},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            _logger.error(
                "Distance delivery: OSRM request failed: %s", exc,
            )
            return False

        if data.get('code') != 'Ok':
            _logger.error(
                "Distance delivery: OSRM returned code=%s (%s)",
                data.get('code'), data.get('message'),
            )
            return False

        try:
            meters = data['routes'][0]['distance']
        except (KeyError, IndexError):
            _logger.error(
                "Distance delivery: unexpected OSRM payload: %s", data,
            )
            return False
        if meters is None:
            return False
        return meters / 1000.0

    # ------------------------------------------------------------------
    # Pricing helpers
    # ------------------------------------------------------------------
    def _distance_select_rule(self, rules, distance):
        """Return the first rule (already ordered) matching the distance."""
        for rule in rules:
            if rule.max_distance_km == 0 or distance <= rule.max_distance_km:
                return rule
        return False

    def _distance_fallback_result(self, message):
        """Build a rate result for the fallback path."""
        self.ensure_one()
        if self.distance_fallback_price > 0:
            return {
                'success': True,
                'price': self.distance_fallback_price,
                'error_message': False,
                'warning_message': message,
                'distance_km': False,
            }
        return {
            'success': False,
            'price': 0.0,
            'error_message': message,
            'warning_message': False,
            'distance_km': False,
        }

    # ------------------------------------------------------------------
    # Rate / shipment API
    # ------------------------------------------------------------------
    def _distance_rate_for_partner(self, dest_partner, origin_partner=None):
        """Rate a delivery to ``dest_partner``, independently of any document.

        This is the single implementation of the distance pricing. The sale
        flow reaches it through :meth:`distance_based_rate_shipment`; the Point
        of Sale calls it directly (there is no ``sale.order`` to rate against),
        so both channels always quote the same price for the same address.

        ``origin_partner`` is optional: leave it out and the carrier's own
        origin (or the company address) is used.

        Returns the same dict shape as ``rate_shipment``: ``success``,
        ``price``, ``error_message``, ``warning_message`` -- plus
        ``distance_km``, which the caller may show to the user.
        """
        self.ensure_one()
        # sudo so public website customers can read the rules.
        rules = self.sudo().rule_ids
        country = dest_partner.country_id

        if not country:
            return self._distance_fallback_result(
                _("No destination country set on the shipping address.")
            )

        country_rules = rules.filtered(
            lambda r: r.country_id.id == country.id
        )
        if not country_rules:
            _logger.info(
                "Distance delivery: no rule for country %s, using fallback.",
                country.name,
            )
            return self._distance_fallback_result(
                _("No pricing rule configured for %s.", country.name)
            )

        if not origin_partner:
            origin_partner = self._distance_default_origin_partner()
        distance = self.sudo()._distance_compute_km(
            origin_partner, dest_partner
        )
        # `False` means the lookup failed; a real 0.0 km (pickup at the store)
        # is a valid distance and must not fall back.
        if distance is False:
            return self._distance_fallback_result(
                _("Could not compute the delivery distance.")
            )

        rule = self._distance_select_rule(country_rules, distance)
        if not rule:
            return self._distance_fallback_result(
                _("No pricing tier matches a distance of %.1f km.", distance)
            )

        block_km = rule.block_km or 1.0
        blocks = max(1, int(ceil(distance / block_km)))
        price = blocks * rule.price_per_block

        warning = _(
            "Distance: %(distance).1f km — %(blocks)s block(s) of "
            "%(block_km).1f km — Price: %(price).2f",
            distance=distance,
            blocks=blocks,
            block_km=block_km,
            price=price,
        )
        _logger.info("Distance delivery: %s", warning)
        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': warning,
            'distance_km': distance,
        }

    def distance_based_rate_shipment(self, order):
        self.ensure_one()
        return self._distance_rate_for_partner(
            order.partner_shipping_id,
            self._distance_get_origin_partner(order),
        )

    def distance_based_send_shipping(self, pickings):
        return [
            {'exact_price': 0.0, 'tracking_number': False}
            for _picking in pickings
        ]

    def distance_based_get_tracking_link(self, picking):
        return False

    def distance_based_cancel_shipment(self, pickings):
        return True
