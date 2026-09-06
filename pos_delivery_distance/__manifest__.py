# -*- coding: utf-8 -*-
{
    'name': 'POS Distance Based Delivery',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Pick a delivery address in the POS and charge the delivery price for any Delivery Method',
    'description': """
POS Distance Based Delivery
===========================

Adds a **Delivery** button to the Point of Sale that lets the cashier pick (or
create) a delivery address for the current customer. Any Delivery Method can
be configured, not just distance-based ones:

* Distance-based carriers are rated through the *very same*
  ``delivery.carrier._distance_rate_for_partner()`` pricing already used by
  the website and the sale flow, so the POS and the webshop can never quote
  different prices for the same address.
* Every other Delivery Method (fixed price, based on rule, third-party
  couriers, ...) is rated through the carrier's own standard
  ``rate_shipment()`` API, the same one the sale flow uses -- just against a
  lightweight stand-in for the ``sale.order`` it normally expects, since
  there is no real sale order in the POS.

The resulting price is dropped on a dedicated "Delivery Service" order line,
using the Delivery Method's own product (``delivery.carrier.product_id``).

* The address is a child contact of the customer, so it is reusable on the next
  order and visible in the backend like any other delivery address.
* On validation the delivery ``stock.picking`` is created against the delivery
  address rather than the invoicing contact.

Configure the Delivery Method under
*Point of Sale > Configuration > Settings > POS Delivery*.
""",
    'author': 'Nabie Alhuda',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'delivery_distance', 'national_address_field', 'stock'],
    'data': [
        'views/delivery_carrier_views.xml',
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
