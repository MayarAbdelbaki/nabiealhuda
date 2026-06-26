# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import os

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Apply the product Weight/Volume values via raw SQL on install.

    The SQL only UPDATEs existing ``product_template`` rows (matched by id and a
    name guard), so it creates no ``ir.model.data`` records. Consequently the
    values survive uninstalling this module.
    """
    sql_path = os.path.join(
        os.path.dirname(__file__), 'data', 'update_product_weight_volume.sql'
    )
    with open(sql_path, encoding='utf-8') as sql_file:
        raw = sql_file.read()

    # Drop comments and transaction control; Odoo manages the transaction itself.
    statements = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('--'):
            continue
        if stripped.upper() in ('BEGIN;', 'COMMIT;', 'ROLLBACK;'):
            continue
        statements.append(line)

    body = '\n'.join(statements).strip()
    if not body:
        _logger.warning('product_weight_volume_init: no SQL statements to run.')
        return

    env.cr.execute(body)
    _logger.info(
        'product_weight_volume_init: applied product weight/volume update SQL.'
    )
