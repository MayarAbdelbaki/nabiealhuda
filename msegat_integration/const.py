# Msegat SMS gateway, see https://documenter.getpostman.com/view/39158411/2sBY4LT3EY
MSEGAT_API_URL = 'https://www.msegat.com/gw/'
MSEGAT_SUCCESS_CODES = {'1', 'M0000'}
MSEGAT_ERROR_MESSAGES = {
    'M0001': "Variables missing",
    'M0002': "Invalid login info",
    'M0008': "The mobile number has an incorrect prefix",
    'M0034': "Please use the POST method",
    'M0037': "Send from a static IP, or disable this restriction in your Msegat account settings",
    'M0090': "The message does not match any template",
    '1010': "Variables missing",
    '1020': "Invalid login info",
    '1050': "Message body is empty",
    '1060': "Balance is not enough",
    '1061': "Message duplicated",
    '1064': "Free OTP: the message must be \"Pin Code is: xxxx\", or activate your sender name",
    '1110': "Sender name is missing or incorrect",
    '1120': "Mobile number is not correct or international messaging is not enabled",
    '1140': "Message is too long",
    '400': "Code expired",
    '404': "Code not found",
}

# Msegat's WhatsApp Business service runs on T2 Communicate, see https://t2techdetails.docs.apiary.io/
WHATSAPP_API_URL = 'https://communicateapi.t2.sa/api'
WHATSAPP_MEDIA_TYPE_DOCUMENT = 5
WHATSAPP_TEMPLATE_VARIABLES = (
    'partner_name', 'invoice_number', 'amount_total', 'amount_residual',
    'invoice_date', 'invoice_date_due', 'company_name',
)

REQUEST_TIMEOUT = 20

OTP_CODE_LENGTH = 4  # Msegat's free OTP sender only accepts "Pin Code is: xxxx"
OTP_VALIDITY_MINUTES = 5
OTP_MAX_ATTEMPTS = 3
OTP_SEND_LIMIT = 5  # codes per user per hour
