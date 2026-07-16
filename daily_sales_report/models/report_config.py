# -*- coding: utf-8 -*-
import base64
import io
import logging
from datetime import datetime, time, timedelta

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
XLSX_COLUMNS = ['Order Ref', 'Customer', 'Product', 'Qty', 'Unit Price', 'Line Total', 'Date/Time']

WEEKDAY_SELECTION = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

PERIODICITY_SELECTION = [
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
]


class DailySalesReportConfig(models.Model):
    """Configuration of a scheduled sales report: what to include, who to
    email it to, and how often to send it."""
    _name = 'daily.sales.report.config'
    _description = 'Daily Sales Report Configuration'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    email_to = fields.Char(
        string='Recipients', required=True,
        help='Comma-separated list of recipient email addresses')
    periodicity = fields.Selection(
        PERIODICITY_SELECTION, required=True, default='daily')
    weekday = fields.Selection(
        WEEKDAY_SELECTION, string='Day of Week',
        help='Day of the week the report is sent, only used when periodicity is Weekly')
    include_pos = fields.Boolean(string='Include POS Orders', default=True)
    include_sales = fields.Boolean(string='Include Sales Orders', default=True)
    include_ecommerce = fields.Boolean(string='Include eCommerce Orders', default=True)
    last_run = fields.Datetime(readonly=True)

    history_ids = fields.One2many('daily.sales.report.history', 'config_id', string='History')
    history_count = fields.Integer(compute='_compute_history_count')

    def _compute_history_count(self):
        for config in self:
            config.history_count = self.env['daily.sales.report.history'].sudo().search_count(
                [('config_id', '=', config.id)])

    def action_view_history(self):
        """Open the history records linked to this configuration."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'daily_sales_report.action_daily_sales_report_history')
        action['domain'] = [('config_id', '=', self.id)]
        action['context'] = {'default_config_id': self.id}
        return action

    # ------------------------------------------------------------
    # Report type registry
    # ------------------------------------------------------------
    def _get_report_specs(self):
        """Return the report types this module can generate.

        Each entry describes: the key used for history fields/attachment
        naming, the config boolean that enables it, its display label, and
        the name of the method that returns its data rows. To add a new
        report type in the future, add an entry here, implement the
        corresponding ``_get_<key>_report_lines`` method, and add matching
        ``<key>_orders_count`` / ``<key>_total`` fields on
        ``daily.sales.report.history``.
        """
        return [
            {'key': 'pos', 'include_field': 'include_pos', 'label': 'POS Orders', 'method': '_get_pos_report_lines'},
            {'key': 'sales', 'include_field': 'include_sales', 'label': 'Sales Orders', 'method': '_get_sales_report_lines'},
            {'key': 'ecommerce', 'include_field': 'include_ecommerce', 'label': 'eCommerce Orders', 'method': '_get_ecommerce_report_lines'},
        ]

    # ------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------
    def _should_send_today(self, today):
        """Return whether this config's report is due to be sent on ``today``."""
        self.ensure_one()
        if self.periodicity == 'daily':
            return True
        if self.periodicity == 'weekly':
            return bool(self.weekday) and str(today.weekday()) == self.weekday
        if self.periodicity == 'monthly':
            return today.day == 1
        return False

    def _get_report_period(self, today):
        """Return the (date_from, date_to) period covered by today's report."""
        self.ensure_one()
        if self.periodicity == 'daily':
            target = today - timedelta(days=1)
            return target, target
        if self.periodicity == 'weekly':
            date_to = today - timedelta(days=1)
            date_from = date_to - timedelta(days=6)
            return date_from, date_to
        # monthly: previous calendar month
        first_of_this_month = today.replace(day=1)
        date_to = first_of_this_month - timedelta(days=1)
        date_from = date_to.replace(day=1)
        return date_from, date_to

    @api.model
    def _cron_send_reports(self):
        """Cron entry point: for every active config due today, build and
        send its report. A failure on one config is logged to history and
        does not prevent the other configs from running."""
        today = fields.Date.context_today(self)
        configs = self.sudo().search([('active', '=', True)])
        for config in configs:
            if not config._should_send_today(today):
                continue
            date_from, date_to = config._get_report_period(today)
            config._send_report_safe(date_from, date_to)

    def action_send_now(self):
        """Manually trigger this configuration's report immediately, for
        testing, ignoring whether today matches its periodicity schedule.
        Uses the same period the config would use on its next scheduled
        run, and shows the result as an on-screen notification."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        date_from, date_to = self._get_report_period(today)
        history = self._send_report_safe(date_from, date_to)
        if history.status == 'sent':
            message = _("Report sent successfully to %s.") % self.email_to
            notif_type = 'success'
        else:
            message = history.error_message or _("Report failed to send.")
            notif_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Daily Sales Report'),
                'message': message,
                'type': notif_type,
                'sticky': notif_type == 'danger',
            },
        }

    def _send_report_safe(self, date_from, date_to):
        """Send the report for the given period, always recording the
        outcome to history whether it succeeds or fails. A failure rolls
        back only this config's partial work (via a savepoint) so it
        cannot affect other configs or callers in the same transaction.
        Returns the created history record either way."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return self._send_report(date_from, date_to)
        except Exception as exc:  # noqa: BLE001 - caller must not be interrupted
            _logger.exception(
                "Daily Sales Report: failed to send report for config '%s'", self.name)
            return self.env['daily.sales.report.history'].sudo().create({
                'config_id': self.id,
                'sent_date': fields.Datetime.now(),
                'date_from': date_from,
                'date_to': date_to,
                'periodicity': self.periodicity,
                'recipients': self.email_to,
                'status': 'failed',
                'error_message': str(exc),
            })

    # ------------------------------------------------------------
    # Report generation / sending
    # ------------------------------------------------------------
    def _send_report(self, date_from, date_to):
        """Gather data, build the XLSX attachments, email them, and log a
        successful history record. Raises on any failure so the caller can
        record it as a failed history entry."""
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()

        attachments = self.env['ir.attachment']
        counts = {}
        totals = {}
        for spec in self._get_report_specs():
            if not self[spec['include_field']]:
                continue
            rows, count, total = getattr(self, spec['method'])(date_from, date_to)
            counts[spec['key']] = count
            totals[spec['key']] = total
            xlsx_data = self._build_xlsx(spec['label'], rows)
            filename = '%s_%s_%s.xlsx' % (spec['key'], date_from, date_to)
            attachments |= Attachment.create({
                'name': filename,
                'datas': base64.b64encode(xlsx_data),
                'type': 'binary',
                'mimetype': XLSX_MIMETYPE,
            })

        if not attachments:
            raise UserError(_("No report type is enabled for '%s': nothing to send.") % self.name)

        self._send_email(attachments)

        history = self.env['daily.sales.report.history'].sudo().create({
            'config_id': self.id,
            'sent_date': fields.Datetime.now(),
            'date_from': date_from,
            'date_to': date_to,
            'periodicity': self.periodicity,
            'recipients': self.email_to,
            'pos_orders_count': counts.get('pos', 0),
            'sales_orders_count': counts.get('sales', 0),
            'ecommerce_orders_count': counts.get('ecommerce', 0),
            'pos_total': totals.get('pos', 0.0),
            'sales_total': totals.get('sales', 0.0),
            'ecommerce_total': totals.get('ecommerce', 0.0),
            'attachment_ids': [(6, 0, attachments.ids)],
            'status': 'sent',
        })
        attachments.write({'res_model': 'daily.sales.report.history', 'res_id': history.id})
        self.last_run = fields.Datetime.now()
        return history

    def _send_email(self, attachments):
        """Send a single email carrying all given attachments to every
        address configured in email_to."""
        self.ensure_one()
        recipients = [email.strip() for email in (self.email_to or '').split(',') if email.strip()]
        if not recipients:
            raise UserError(_("Report '%s' has no recipient email configured.") % self.name)

        mail = self.env['mail.mail'].sudo().create({
            'subject': _('Daily Sales Report - %s') % self.name,
            'email_from': self._get_email_from(),
            'email_to': ','.join(recipients),
            'body_html': _(
                '<p>Please find attached the sales reports for <b>%(name)s</b>.</p>'
            ) % {'name': self.name},
            'attachment_ids': [(6, 0, attachments.ids)],
            'auto_delete': False,
        })
        mail.send()

    def _get_email_from(self):
        """Return the From address to use for report emails.

        The cron may run as a technical user (e.g. OdooBot) whose own email
        does not match the account authenticated on the outgoing mail
        server, which some providers (e.g. Gmail) reject or rewrite. Using
        the configured server's own SMTP username guarantees the two match.
        """
        mail_server = self.env['ir.mail_server'].sudo().search([], order='sequence', limit=1)
        return mail_server.smtp_user or self.env.company.email or self.env.user.email

    # ------------------------------------------------------------
    # XLSX building
    # ------------------------------------------------------------
    def _build_xlsx(self, sheet_name, rows):
        """Build an XLSX file (as bytes) with the standard report columns
        from a list of row dicts (order_ref, customer, product, qty,
        unit_price, line_total, date)."""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(sheet_name[:31])

        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})

        for col, header in enumerate(XLSX_COLUMNS):
            sheet.write(0, col, header, header_format)

        for row_idx, row in enumerate(rows, start=1):
            sheet.write(row_idx, 0, row.get('order_ref') or '')
            sheet.write(row_idx, 1, row.get('customer') or '')
            sheet.write(row_idx, 2, row.get('product') or '')
            sheet.write(row_idx, 3, row.get('qty') or 0.0)
            sheet.write(row_idx, 4, row.get('unit_price') or 0.0)
            sheet.write(row_idx, 5, row.get('line_total') or 0.0)
            order_date = row.get('date')
            if order_date:
                sheet.write_datetime(row_idx, 6, order_date, date_format)
            else:
                sheet.write(row_idx, 6, '')

        for col, width in enumerate([18, 24, 30, 8, 12, 14, 20]):
            sheet.set_column(col, col, width)

        workbook.close()
        return output.getvalue()

    # ------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------
    @staticmethod
    def _get_datetime_bounds(date_from, date_to):
        """Convert a (date_from, date_to) pair into naive datetime bounds
        covering the whole days, as strings for use in ORM domains."""
        dt_from = datetime.combine(date_from, time.min)
        dt_to = datetime.combine(date_to, time.max)
        return fields.Datetime.to_string(dt_from), fields.Datetime.to_string(dt_to)

    def _get_pos_report_lines(self, date_from, date_to):
        """Return (rows, order_count, amount_total) for POS orders in the period."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['pos.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ('paid', 'done', 'invoiced')),
        ])
        rows = []
        for order in orders:
            for line in order.lines:
                rows.append({
                    'order_ref': order.pos_reference or order.name,
                    'customer': order.partner_id.name or '',
                    'product': line.product_id.display_name,
                    'qty': line.qty,
                    'unit_price': line.price_unit,
                    'line_total': line.price_subtotal_incl,
                    'date': order.date_order,
                })
        return rows, len(orders), sum(orders.mapped('amount_total'))

    def _get_sales_report_lines(self, date_from, date_to):
        """Return (rows, order_count, amount_total) for confirmed Sales
        orders (excluding website/eCommerce orders) in the period."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['sale.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', '=', 'sale'),
            ('website_id', '=', False),
        ])
        rows = self._sale_order_lines_to_rows(orders)
        return rows, len(orders), sum(orders.mapped('amount_total'))

    def _get_ecommerce_report_lines(self, date_from, date_to):
        """Return (rows, order_count, amount_total) for confirmed website
        (eCommerce) Sales orders in the period."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['sale.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', '=', 'sale'),
            ('website_id', '!=', False),
        ])
        rows = self._sale_order_lines_to_rows(orders)
        return rows, len(orders), sum(orders.mapped('amount_total'))

    @staticmethod
    def _sale_order_lines_to_rows(orders):
        """Flatten sale.order lines (skipping section/note lines) into report rows."""
        rows = []
        for order in orders:
            for line in order.order_line.filtered(lambda l: not l.display_type):
                rows.append({
                    'order_ref': order.name,
                    'customer': order.partner_id.name or '',
                    'product': line.product_id.display_name,
                    'qty': line.product_uom_qty,
                    'unit_price': line.price_unit,
                    'line_total': line.price_subtotal,
                    'date': order.date_order,
                })
        return rows
