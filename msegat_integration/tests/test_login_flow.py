import re
from urllib.parse import urlsplit

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.msegat_integration.tests.common import mock_msegat


def sms_sent(payload):
    return {'code': '1', 'message': 'Success'}


@tagged('post_install', '-at_install')
class TestMsegatLoginFlow(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Free sign up, set on the websites when website is installed
        cls.env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')
        if 'website' in cls.env:
            cls.env['website'].search([]).auth_signup_uninvited = 'b2c'
        cls.env.company.write({
            'country_id': cls.env.ref('base.sa').id,
            'msegat_username': 'odoo',
            'msegat_api_key': 'secret',
            'msegat_sender': 'auth-mseg',
            'msegat_otp_login': True,
            'msegat_otp_method': 'sms',
        })
        cls.portal_user = new_test_user(cls.env, login='msegat_portal', groups='base.group_portal')
        cls.portal_user.partner_id.phone = '050 123 4567'
        internal_user = new_test_user(cls.env, login='msegat_internal', groups='base.group_user')
        internal_user.partner_id.phone = '050 123 4568'

    def _csrf_token(self, response):
        return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)

    def _post(self, url, response, **data):
        return self.url_open(url, data={**data, 'csrf_token': self._csrf_token(response)})

    def _login(self, login):
        self.opener.cookies.clear()
        return self._post('/web/login', self.url_open('/web/login'), login=login, password=login)

    def _code(self, call):
        return call['json']['msg'].rsplit(' ', 1)[1]

    def _wrong_code(self, code):
        return str((int(code) + 1) % 10000).zfill(4)

    def test_signup_verifies_phone(self):
        with mock_msegat({'sendsms.php': sms_sent}) as calls:
            response = self._post(
                '/web/signup', self.url_open('/web/signup'),
                login='new.customer@example.com', name="New Customer",
                password='new.customer@example.com', confirm_password='new.customer@example.com',
            )
            self.assertEqual(urlsplit(response.url).path, '/web/login/msegat_otp')
            self.assertIn('name="phone"', response.text)
            self.assertFalse(calls)

            response = self._post('/web/login/msegat_otp', response, phone='12')
            self.assertIn('Please enter a valid mobile number', response.text)
            self.assertFalse(calls)

            response = self._post('/web/login/msegat_otp', response, phone='055 987 6543')
            self.assertEqual(calls[0]['json']['numbers'], '966559876543')
            code = self._code(calls[0])

            response = self._post('/web/login/msegat_otp', response, otp_code=self._wrong_code(code))
            self.assertIn('invalid or has expired', response.text)

            response = self._post('/web/login/msegat_otp', response, otp_code=code)
            self.assertNotIn('/web/login', urlsplit(response.url).path)

            user = self.env['res.users'].search([('login', '=', 'new.customer@example.com')])
            self.assertEqual(user.partner_id.phone, '+966559876543')
            self.assertFalse(user.msegat_verify_phone)

            response = self._login('new.customer@example.com')
            self.assertNotIn('/web/login', urlsplit(response.url).path, "No code at the next logins")
            self.assertEqual(len(calls), 1)

    def test_first_login_uses_number_on_file(self):
        with mock_msegat({'sendsms.php': sms_sent}) as calls:
            response = self._login('msegat_portal')
            self.assertEqual(urlsplit(response.url).path, '/web/login/msegat_otp')
            self.assertEqual(calls[0]['json']['numbers'], '966501234567')
            self.assertIn('4567', response.text)

            response = self.url_open('/web/login/msegat_otp')
            self.assertEqual(len(calls), 1, "Reloading the page must not send another code")

            response = self._post('/web/login/msegat_otp', response, resend='1')
            self.assertEqual(len(calls), 2)

            # The customer can switch to another number before verifying.
            response = self._post('/web/login/msegat_otp', response, change_number='1')
            self.assertIn('name="phone"', response.text)
            response = self.url_open('/web/login/msegat_otp')
            self.assertIn('name="phone"', response.text)
            self.assertEqual(len(calls), 2)
            response = self._post('/web/login/msegat_otp', response, phone='0559876543')
            self.assertEqual(calls[2]['json']['numbers'], '966559876543')

            response = self._post('/web/login/msegat_otp', response, otp_code=self._code(calls[2]))
            self.assertNotIn('/web/login', urlsplit(response.url).path)
        self.assertEqual(urlsplit(self.url_open('/my').url).path, '/my', "The portal user is logged in")
        self.assertEqual(self.portal_user.partner_id.phone, '+966559876543')

    def test_internal_login_unchanged(self):
        with mock_msegat({}) as calls:
            response = self._login('msegat_internal')
        self.assertTrue(urlsplit(response.url).path.startswith('/odoo'))
        self.assertFalse(calls)
