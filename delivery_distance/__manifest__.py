# -*- coding: utf-8 -*-
{
    'name': 'Distance Based Delivery',
    'version': '19.0.2.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Compute shipping cost from driving distance via OSRM (free)',
    'description': """
Distance Based Delivery
=======================

Adds a new delivery carrier provider ``Based on Distance`` that calculates the
shipping cost from the road distance (OSRM routing, free and key-less) between
the store/origin address and the customer's shipping address. Coordinates are
resolved from the partner's geolocation or via Nominatim.

Each carrier holds a table of per-country pricing rules. The distance is split
into charge blocks (e.g. 25 SR for every started 18 km) and tiers can be built
per country using an optional maximum distance.
""",
    'author': 'Mayar',
    'license': 'LGPL-3',
    'depends': ['delivery', 'base_geolocalize', 'website_sale', 'sale', 'national_address_field'],
    'data': [
        'security/ir.model.access.csv',
        'views/delivery_carrier_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/website_address_templates.xml',
        'report/sale_order_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'delivery_distance/static/src/scss/osm_map_location.scss',
            'delivery_distance/static/src/js/osm_map_location.js',
            'delivery_distance/static/src/xml/osm_map_location.xml',
        ],
        'web.assets_frontend': [
            'delivery_distance/static/src/scss/checkout_map.scss',
            'delivery_distance/static/src/js/checkout_map.js',
        ],
    },
    'installable': True,
    'application': False,
}
