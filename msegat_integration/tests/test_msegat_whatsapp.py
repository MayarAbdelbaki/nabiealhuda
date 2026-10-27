from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import formatLang

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.msegat_integration.models import res_company
from odoo.addons.msegat_integration.tests.common import mock_msegat

PDF = b'%PDF-1.4 invoice'


@tagged('post_install', '-at_install')
class TestMsegatWhatsapp(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://erp.example.com')
        cls.company = cls.company_data['company']
        cls.company.write({
            'msegat_whatsapp_email': 'odoo@example.com',
            'msegat_whatsapp_password': 'secret',
            'msegat_whatsapp_template': 'invoice_pdf',
        })
        cls.partner_a.phone = '+966 50 123 4567'
        cls.invoice = cls.init_invoice('out_invoice', partner=cls.partner_a, amounts=[100], post=True)

    def setUp(self):
        super().setUp()
        res_company._whatsapp_tokens.clear()
        patcher = patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf', return_value=(PDF, 'pdf'))
        self.render_pdf = patcher.start()
        self.addCleanup(patcher.stop)

    def _handlers(self, send=None):
        return {
            '/auth/login': lambda payload: {'token': 'jwt-token', 'expireInSeconds': 3600},
            '/message/send-custom': send or (lambda payload: {'id': 'conversation-1', 'messageId': 'wamid.1'}),
        }

    def _check_public_link(self, url):
        """ Check WhatsApp can download `url` without logging in, and return the attachment. """
        self.assertTrue(url.startswith('https://erp.example.com/web/content/'), url)
        parts = urlsplit(url)
        attachment_id = int(parts.path.rsplit('/', 1)[1])
        token = parse_qs(parts.query)['access_token'][0]
        Binary = self.env['ir.binary'].with_user(self.env.ref('base.public_user'))
        attachment = Binary._find_record(res_id=attachment_id, access_token=token, field='raw')
        wrong_token = ('a' if token[0] != 'a' else 'b') + token[1:]
        with self.assertRaises(AccessError):
            Binary._find_record(res_id=attachment_id, access_token=wrong_token, field='raw')
        return attachment

    def test_send_invoice_template(self):
        with mock_msegat(self._handlers()) as calls:
            action = self.invoice.action_msegat_send_whatsapp()
        self.assertEqual(action['params']['type'], 'success')

        login, send = calls
        self.assertEqual(login['url'], 'https://communicateapi.t2.sa/api/auth/login')
        self.assertEqual(login['json'], {'email': 'odoo@example.com', 'password': 'secret'})
        self.assertEqual(send['url'], 'https://communicateapi.t2.sa/api/message/send-custom')
        self.assertEqual(send['headers'], {'Authorization': 'Bearer jwt-token'})

        payload = send['json']
        self.assertEqual(payload['recipient'], {'id': '966501234567'})
        self.assertIsNone(payload['media'])
        text = payload['message']['text'].split('##')
        self.assertEqual(text[:4], ['', 'invoice_pdf', 'partner_a', self.invoice.name])
        self.assertEqual(len(text), 6, "template, 3 variables, and the ## delimiters around them")
        self.assertEqual(text[4], formatLang(self.env, self.invoice.amount_total, currency_obj=self.invoice.currency_id))

        document = payload['message']['quick_replies'][0]
        self.assertEqual(document['content_type'], 'document')
        attachment = self._check_public_link(document['payload'])
        self.assertEqual(document['title'], attachment.name)
        self.assertEqual(attachment.raw, PDF)
        self.assertEqual((attachment.res_model, attachment.res_id), ('account.move', self.invoice.id))
        self.assertIn('wamid.1', self.invoice.message_ids[0].body)

    def test_send_invoice_document(self):
        self.company.msegat_whatsapp_mode = 'document'
        with mock_msegat(self._handlers()) as calls:
            self.invoice.action_msegat_send_whatsapp()
        payload = calls[1]['json']
        self.assertIsNone(payload['message'])
        media = payload['media']
        self.assertEqual((media['mediaType'], media['contentType']), (5, 'application/pdf'))
        self.assertEqual(media['size'], len(PDF))
        self.assertEqual(self._check_public_link(media['url']).name, media['name'])

    def test_reuse_legal_pdf(self):
        legal_pdf = self.env['ir.attachment'].create({
            'name': 'INV_legal.pdf',
            'raw': b'%PDF-1.4 legal',
            'mimetype': 'application/pdf',
            'res_model': 'account.move',
            'res_id': self.invoice.id,
            'res_field': 'invoice_pdf_report_file',
        })
        self.invoice.invalidate_recordset(['invoice_pdf_report_id'])
        with mock_msegat(self._handlers()) as calls:
            self.invoice.action_msegat_send_whatsapp()
        self.render_pdf.assert_not_called()
        self.assertEqual(self._check_public_link(calls[1]['json']['message']['quick_replies'][0]['payload']), legal_pdf)

    def test_resend_replaces_pdf(self):
        with mock_msegat(self._handlers()) as calls:
            self.invoice.action_msegat_send_whatsapp()
            self.invoice.action_msegat_send_whatsapp()
        self.assertEqual(len(calls), 3, "Logged in once, then the token is reused")
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'), ('res_id', '=', self.invoice.id), ('description', '=', 'msegat_whatsapp'),
        ])
        self.assertEqual(len(attachments), 1)

    def test_token_revoked(self):
        responses = iter([({'message': None}, 401), {'id': 'conversation-1', 'messageId': 'wamid.2'}])
        with mock_msegat(self._handlers(send=lambda payload: next(responses))) as calls:
            self.invoice.action_msegat_send_whatsapp()
        self.assertEqual([call['url'].rsplit('/', 1)[1] for call in calls], ['login', 'send-custom'] * 2)
        self.assertIn('wamid.2', self.invoice.message_ids[0].body)

    def test_api_error(self):
        send = lambda payload: ({'success': False, 'message': 'Template not found'}, 400)  # noqa: E731
        with mock_msegat(self._handlers(send=send)), self.assertRaisesRegex(UserError, 'Template not found'):
            self.invoice.action_msegat_send_whatsapp()

    def test_local_base_url(self):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://localhost:8069')
        with mock_msegat({}) as calls, self.assertRaisesRegex(UserError, 'not reachable from the internet'):
            self.invoice.action_msegat_send_whatsapp()
        self.assertFalse(calls)

    def test_invalid_invoices(self):
        draft = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[50])
        with self.assertRaises(UserError):
            draft.action_msegat_send_whatsapp()
        self.partner_a.phone = False
        with self.assertRaisesRegex(UserError, 'no valid phone number'):
            self.invoice.action_msegat_send_whatsapp()

    def test_send_several_invoices(self):
        other_invoice = self.init_invoice('out_invoice', partner=self.partner_b, amounts=[50], post=True)
        with mock_msegat(self._handlers()):
            action = (self.invoice + other_invoice).action_msegat_send_whatsapp()
        self.assertEqual(action['params']['type'], 'warning')
        self.assertIn(other_invoice.name, action['params']['message'])
        self.assertIn('wamid.1', self.invoice.message_ids[0].body)
        self.assertFalse(other_invoice.message_ids.filtered(lambda m: 'WhatsApp' in (m.body or '')))
