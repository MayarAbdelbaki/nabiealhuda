# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""One-time cleanup of Odoo's original Saudi Arabia ``res.country.state``
seed data (93 records that are actually city names, unrelated to the 14 real
admin regions this module now loads via ``data/res_country_state_ksa.csv``).

Runs after that CSV has already been loaded, so the new region rows (each
owned by this module via ``ir.model.data``) already exist. Any Saudi state
row NOT owned by this module is one of the old seed rows: partners pointing
at it are cleared (logged for manual follow-up), then the row is deleted.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT s.id
        FROM res_country_state s
        JOIN res_country c ON c.id = s.country_id
        WHERE c.code = 'SA'
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data d
              WHERE d.model = 'res.country.state'
                AND d.res_id = s.id
                AND d.module = 'national_address_field'
          )
    """)
    old_state_ids = [row[0] for row in cr.fetchall()]
    if not old_state_ids:
        return

    cr.execute("""
        SELECT id, name FROM res_partner WHERE state_id = ANY(%s)
    """, (old_state_ids,))
    affected_partners = cr.fetchall()
    if affected_partners:
        _logger.warning(
            "national_address_field: clearing state_id on %d partner(s) whose Saudi "
            "region no longer exists (replaced by the real 14 regions): %s",
            len(affected_partners), affected_partners,
        )

    cr.execute("UPDATE res_partner SET state_id = NULL WHERE state_id = ANY(%s)", (old_state_ids,))
    cr.execute("DELETE FROM res_country_state WHERE id = ANY(%s)", (old_state_ids,))
