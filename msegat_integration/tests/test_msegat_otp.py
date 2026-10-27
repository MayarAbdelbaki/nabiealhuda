from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.msegat_integration.models import res_company
from odoo.addons.msegat_integration.tests.common import mock_msegat, mock_response


def sms_sent(payload):
    return {'code': '1', 'message': 'Success'}


@tagged('post_install', '-at_install')
class TestMsegatOtp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'country_id': cls.env.ref('base.sa').id,
            'msegat_username': 'odoo',
            'msegat_api_key': 'secret',
            'msegat_sender': 'auth-mseg',
            'msegat_otp_login': True,
        })
        cls.portal_user = new_test_user(cls.env, login='msegat_portal', groups='base.group_portal')
        cls.portal_user.partner_id.phone = '050 123 4567'
        cls.internal_user = new_test_user(cls.env, login='msegat_internal', groups='base.group_user')
        cls.internal_user.partner_id.phone = '050 123 4568'
        cls.Otp = cls.env['msegat.otp']

    def _send_odoo_code(self, user=None, new_number=False):
        self.company.msegat_otp_method = 'sms'
        with mock_msegat({'sendsms.php': sms_sent}) as calls:
            otp = self.Otp._send_code(user or self.portal_user, new_number=new_number)
        message = calls[0]['json']['msg']
        self.assertRegex(message, r'^Pin Code is: \d{4}$')
        self.assertEqual(calls[0]['json']['numbers'], otp.number)
        return otp, message.rsplit(' ', 1)[1]

    def test_phone_number_format(self):
        partner = self.portal_user.partner_id
        for phone in ('050 123 4567', '+966 50 123 4567', '00966501234567', '966501234567'):
            partner.phone = phone
            self.assertEqual(partner._msegat_number(self.company.country_id), '966501234567', phone)
        self.assertEqual(partner._msegat_number(self.company.country_id, number='0559876543'), '966559876543')
        for phone in (False, '123', 'not a number'):
            partner.phone = phone
            self.assertFalse(partner._msegat_number(self.company.country_id), phone)

    def test_new_external_users_verify_once(self):
        self.assertTrue(self.portal_user.msegat_verify_phone)
        self.assertFalse(self.internal_user.msegat_verify_phone)
        self.assertEqual(self.portal_user._mfa_type(), 'msegat_otp')
        self.assertEqual(self.portal_user._mfa_url(), '/web/login/msegat_otp')
        self.assertTrue(self.portal_user._rpc_api_keys_only())
        self.assertNotEqual(self.internal_user._mfa_type(), 'msegat_otp')

        otp, code = self._send_odoo_code()
        self.portal_user._check_credentials({'type': 'msegat_otp', 'otp_id': otp.id, 'code': code}, {'interactive': True})
        self.assertFalse(self.portal_user.msegat_verify_phone)
        self.assertNotEqual(self.portal_user._mfa_type(), 'msegat_otp', "Later logins only need the password")
        self.assertFalse(self.portal_user._rpc_api_keys_only())
        self.assertEqual(self.portal_user.partner_id.phone, '050 123 4567', "The verified number was already on file")

    def test_existing_users_not_asked(self):
        self.company.msegat_otp_login = False
        user = new_test_user(self.env, login='msegat_before', groups='base.group_portal')
        self.company.msegat_otp_login = True
        self.assertFalse(user.msegat_verify_phone)
        self.assertNotEqual(user._mfa_type(), 'msegat_otp')

        user.msegat_verify_phone = True
        self.assertEqual(user._mfa_type(), 'msegat_otp', "An admin can ask a user to verify their phone")

        self.company.msegat_otp_login = False
        self.assertNotEqual(user._mfa_type(), 'msegat_otp')

    def test_add_missing_number(self):
        self.portal_user.partner_id.phone = '123'
        with self.assertRaisesRegex(UserError, 'Enter your mobile number'):
            self.Otp._send_code(self.portal_user)

        otp, code = self._send_odoo_code(new_number='966559876543')
        self.assertEqual(otp.number, '966559876543')
        self.portal_user._check_credentials({'type': 'msegat_otp', 'otp_id': otp.id, 'code': code}, {'interactive': True})
        self.assertEqual(self.portal_user.partner_id.phone, '+966559876543')

    def test_use_another_number(self):
        otp, code = self._send_odoo_code(new_number='966559876543')
        self.assertEqual(otp.number, '966559876543')
        self.portal_user._check_credentials({'type': 'msegat_otp', 'otp_id': otp.id, 'code': code}, {'interactive': True})
        self.assertEqual(self.portal_user.partner_id.phone, '+966559876543', "The verified number replaces the old one")

    def test_msegat_otp_service(self):
        def verify(payload):
            if payload['code'] == '4321':
                return {'code': '1', 'message': 'Success'}
            return {'code': '404', 'message': 'Code not found'}

        with mock_msegat({
            'sendOTPCode.php': lambda payload: {'id': 77, 'success': True, 'code': '1', 'message': 'Success'},
            'verifyOTPCode.php': verify,
        }) as calls:
            otp = self.Otp._send_code(self.portal_user)
            self.assertEqual(otp.msegat_code_id, '77')
            self.assertEqual(calls[0]['json'], {
                'userName': 'odoo',
                'apiKey': 'secret',
                'number': '966501234567',
                'userSender': 'auth-mseg',
                'lang': 'Ar',
            })

            self.assertFalse(otp._verify('1111'))
            self.assertEqual(otp.attempts, 1)
            self.assertTrue(otp._verify('4321'))
            self.assertEqual(otp.state, 'verified')
            self.assertEqual(calls[-1]['json']['id'], 77)
            self.assertFalse(otp._verify('4321'), "A code can be used only once")

    def test_odoo_code(self):
        otp, code = self._send_odoo_code()
        wrong_code = str((int(code) + 1) % 10000).zfill(4)
        self.assertFalse(otp._verify(wrong_code))
        self.assertTrue(otp._verify(f' {code} '))
        self.assertEqual(otp.state, 'verified')

    def test_max_attempts(self):
        otp, code = self._send_odoo_code()
        wrong_code = str((int(code) + 1) % 10000).zfill(4)
        for _i in range(3):
            self.assertFalse(otp._verify(wrong_code))
        self.assertEqual(otp.state, 'failed')
        self.assertFalse(otp._verify(code))

    def test_expiry(self):
        otp, code = self._send_odoo_code()
        with freeze_time(fields.Datetime.now() + timedelta(minutes=6)):
            self.assertFalse(otp._verify(code))

    def test_send_limit(self):
        with mock_msegat({'sendOTPCode.php': lambda payload: {'id': 1, 'code': '1'}}):
            for _i in range(5):
                self.Otp._send_code(self.portal_user)
            with self.assertRaises(UserError):
                self.Otp._send_code(self.portal_user)

    def test_msegat_error(self):
        with (
            mock_msegat({'sendOTPCode.php': lambda payload: {'code': 'M0002', 'message': 'Invalid login info'}}),
            self.assertRaisesRegex(UserError, 'Invalid login info'),
        ):
            self.Otp._send_code(self.portal_user)

    def test_check_credentials(self):
        otp, code = self._send_odoo_code()
        other_user = new_test_user(self.env, login='msegat_portal_2', groups='base.group_portal')
        with self.assertRaises(AccessDenied):
            other_user._check_credentials({'type': 'msegat_otp', 'otp_id': otp.id, 'code': code}, {'interactive': True})
        # What a crafted /web/login POST with type=msegat_otp would give
        with self.assertRaises(AccessDenied):
            self.portal_user._check_credentials({'type': 'msegat_otp', 'login': 'msegat_portal'}, {'interactive': True})
        self.assertEqual(otp.attempts, 0)

        auth_info = self.portal_user._check_credentials(
            {'type': 'msegat_otp', 'otp_id': otp.id, 'code': code}, {'interactive': True},
        )
        self.assertEqual(auth_info, {'uid': self.portal_user.id, 'auth_method': 'msegat_otp', 'mfa': 'default'})

    def test_settings_constraints(self):
        with self.assertRaises(ValidationError):
            self.company.write({'msegat_otp_method': 'sms', 'msegat_otp_message': "Your code"})
        with self.assertRaises(ValidationError):
            self.company.msegat_whatsapp_template_params = 'partner_name,unknown_value'

    def test_balance(self):
        with patch.object(res_company.requests, 'get', return_value=mock_response('272.6')):
            self.assertEqual(self.company._msegat_get_balance(), 272.6)
        with (
            patch.object(res_company.requests, 'get', return_value=mock_response('M0002')),
            self.assertRaisesRegex(UserError, 'Invalid login info'),
        ):
            self.company._msegat_get_balance()
