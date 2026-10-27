# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ipaddress
from urllib.parse import urlsplit

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import format_date, formatLang

from odoo.addons.msegat_integration import const

WHATSAPP_ATTACHMENT_DESCRIPTION = 'msegat_whatsapp'


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_msegat_send_whatsapp(self):
        invalid_moves = self.filtered(lambda m: m.state != 'posted' or not m.is_sale_document(include_receipts=True))
        if invalid_moves:
            raise UserError(_(
                "Only posted customer invoices and credit notes can be sent by WhatsApp:\n%s",
                '\n'.join(invalid_moves.mapped('display_name')),
            ))

        if len(self) == 1:
            self._msegat_send_whatsapp()
            return self._msegat_notification('success', _("Invoice sent by WhatsApp."))

        errors = []
        for move in self:
            try:
                with self.env.cr.savepoint():
                    move._msegat_send_whatsapp()
            except UserError as e:
                errors.append(f"{move.name}: {e}")
        sent_count = len(self) - len(errors)
        if not errors:
            return self._msegat_notification('success', _("%s invoices sent by WhatsApp.", sent_count))
        return self._msegat_notification('warning', _(
            "%(sent)s invoices sent by WhatsApp, %(failed)s failed:\n%(errors)s",
            sent=sent_count, failed=len(errors), errors='\n'.join(errors),
        ), sticky=True)

    def _msegat_notification(self, notification_type, message, sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': message,
                'sticky': sticky,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _msegat_send_whatsapp(self):
        """ Send the invoice PDF to the customer's phone number by WhatsApp and log it in the chatter. """
        self.ensure_one()
        company = self.company_id
        number = self.partner_id._msegat_number(company.country_id)
        if not number:
            raise UserError(_("%s has no valid phone number to send the invoice to.", self.partner_id.display_name))
        attachment = self._msegat_whatsapp_attachment()
        url = self._msegat_whatsapp_document_url(attachment)
        customer_lang = self.partner_id.lang or self.env.lang

        if company.msegat_whatsapp_mode == 'template':
            if not company.msegat_whatsapp_template:
                raise UserError(_("Set the WhatsApp template to use for invoices in the Settings."))
            params = self.with_context(lang=customer_lang)._msegat_whatsapp_template_params()
            payload = {
                'recipient': {'id': number},
                'message': {
                    # T2 Communicate syntax for templates: ##template##variable 1##variable 2##
                    'text': '##%s##' % '##'.join([company.msegat_whatsapp_template, *params]),
                    'quick_replies': [{
                        'title': attachment.name,
                        'content_type': 'document',
                        'payload': url,
                        'order': 0,
                    }],
                    'carousel_cards': [],
                    'list_picker': None,
                    'cta_url_button': None,
                },
                'media': None,
            }
        else:
            payload = {
                'recipient': {'id': number},
                'message': None,
                'media': {
                    'contentType': 'application/pdf',
                    'url': url,
                    'size': attachment.file_size,
                    'name': attachment.name,
                    'mediaType': const.WHATSAPP_MEDIA_TYPE_DOCUMENT,
                    'caption': self.with_context(lang=customer_lang).env._("Invoice %s", self.name),
                },
            }

        result = company._msegat_whatsapp_send(payload)
        self.message_post(body=_(
            "Invoice sent by WhatsApp to +%(number)s (message %(message_id)s).",
            number=number,
            message_id=result.get('messageId') or result.get('id') or '-',
        ))

    def _msegat_whatsapp_attachment(self):
        """ Return the invoice PDF: the legal one if it was already generated, else a new rendering of it. """
        self.ensure_one()
        if self.invoice_pdf_report_id:
            return self.invoice_pdf_report_id
        report = self.env['account.move.send']._get_default_pdf_report_id(self) or self.env.ref('account.account_invoices')
        content, _report_type = self.env['ir.actions.report'].with_company(self.company_id).with_context(
            report_pdf_no_attachment=True,
        )._render_qweb_pdf(report, self.ids)
        Attachment = self.env['ir.attachment'].sudo()
        Attachment.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('description', '=', WHATSAPP_ATTACHMENT_DESCRIPTION),
        ]).unlink()
        return Attachment.create({
            'name': self._get_invoice_report_filename(report=report),
            'raw': content,
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
            'description': WHATSAPP_ATTACHMENT_DESCRIPTION,
        })

    def _msegat_whatsapp_document_url(self, attachment):
        """ Return a link to `attachment` that WhatsApp can download without logging in. """
        base_url = self.get_base_url()
        host = urlsplit(base_url).hostname or ''
        try:
            is_local = not ipaddress.ip_address(host).is_global
        except ValueError:
            is_local = host == 'localhost' or '.' not in host or host.endswith('.local')
        if is_local:
            raise UserError(_(
                "WhatsApp downloads the invoice from %s, which is not reachable from the internet. "
                "Set the public address of this Odoo in the web.base.url system parameter.",
                base_url,
            ))
        return f"{base_url}/web/content/{attachment.id}?access_token={attachment._get_raw_access_token()}&download=true"

    def _msegat_whatsapp_template_params(self):
        self.ensure_one()
        values = {
            'partner_name': self.partner_id.name,
            'invoice_number': self.name,
            'amount_total': formatLang(self.env, self.amount_total, currency_obj=self.currency_id),
            'amount_residual': formatLang(self.env, self.amount_residual, currency_obj=self.currency_id),
            'invoice_date': format_date(self.env, self.invoice_date),
            'invoice_date_due': format_date(self.env, self.invoice_date_due),
            'company_name': self.company_id.name,
        }
        # '#' delimits the template variables and WhatsApp rejects line breaks in them.
        return [
            str(values[key] or '').replace('#', '').replace('\n', ' ')
            for key in self.company_id._msegat_whatsapp_template_keys()
        ]
