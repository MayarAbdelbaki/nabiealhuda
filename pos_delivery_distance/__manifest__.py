# -*- coding: utf-8 -*-
{
    'name': 'POS Distance Based Delivery',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Pick a delivery address in the POS and charge the distance-based delivery price',
    'description': """
POS Distance Based Delivery
===========================

Adds a **Delivery** button to the Point of Sale that lets the cashier pick (or
create) a delivery address for the current customer. Selecting an address rates
it through the *very same* ``delivery.distance.rule`` pricing already used by
the website and the sale flow, and drops the resulting price on a dedicated
"Delivery Service" order line.

* The address is a child contact of the customer, so it is reusable on the next
  order and visible in the backend like any other delivery address.
* The price comes from ``delivery.carrier._distance_rate_for_partner()`` -- one
  implementation shared with ``delivery_distance``, so the POS and the webshop
  can never quote different prices for the same address.
* On validation the delivery ``stock.picking`` is created against the delivery
  address rather than the invoicing contact.

Configure the delivery product and the carrier under
*Point of Sale > Configuration > Settings > Distance Delivery*.
""",
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'delivery_distance', 'national_address_field', 'stock'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_delivery_distance/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
