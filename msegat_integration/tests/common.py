import json
from contextlib import contextmanager
from unittest.mock import patch

import requests

from odoo.addons.msegat_integration.models import res_company


def mock_response(data, status=200):
    response = requests.models.Response()
    response.status_code = status
    response.reason = 'OK' if status < 400 else 'Error'
    response._content = (data if isinstance(data, str) else json.dumps(data)).encode()
    return response


@contextmanager
def mock_msegat(handlers):
    """ Replace the Msegat and WhatsApp HTTP API by `handlers`.

    :param dict handlers: {url suffix: function(json payload) -> data or (data, http status)}
    :return: the list of the requests made, as dicts with the keys url, json and headers
    """
    calls = []

    def post(url, **kwargs):
        calls.append({'url': url, 'json': kwargs.get('json'), 'headers': kwargs.get('headers') or {}})
        for suffix, handler in handlers.items():
            if url.endswith(suffix):
                result = handler(kwargs.get('json'))
                data, status = result if isinstance(result, tuple) else (result, 200)
                return mock_response(data, status)
        raise AssertionError(f"Unexpected request to {url}")

    with patch.object(res_company.requests, 'post', side_effect=post):
        yield calls
