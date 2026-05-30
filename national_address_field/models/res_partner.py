# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_national_address = fields.Char(
        string="العنوان الوطني",
        help="Saudi National Address. Shown only when the country is Saudi Arabia.",
    )

    @api.model
    def _get_frontend_writable_fields(self):
        """Allow the national address field to be written from the frontend.

        Odoo's portal/eCommerce address handling (``_parse_form_data`` in the
        portal controller, used by both ``/my/account`` and ``/shop/address``)
        only persists a submitted form key when it is both a real partner field
        and part of this whitelist. Adding our field here is therefore all that
        is needed for the value to reach ``partner.write()`` on either form.
        """
        writable_fields = super()._get_frontend_writable_fields()
        return writable_fields | {'x_national_address'}
