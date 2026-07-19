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
UNPAID_METHOD_LABEL = 'Not Paid Yet'

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
            report_data, count, total = getattr(self, spec['method'])(date_from, date_to)
            counts[spec['key']] = count
            totals[spec['key']] = total
            xlsx_data = self._build_xlsx(spec['label'], report_data)
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
    def _build_xlsx(self, label, report_data):
        """Build an XLSX file (as bytes) for one report type, as a single
        sheet with three sections stacked vertically, each separated by a
        divider bar:

        1. Invoice Details: one row per order/invoice with its customer,
           total amount, and how much of it was paid through each payment
           method (one column per method configured in the system, even if
           unused this period).
        2. Products: every product sold in the period with the total
           quantity sold, aggregated across all orders.
        3. Payment Totals: the grand total collected through each payment
           method across all orders in the period.

        ``report_data`` is the dict produced by the ``_get_<key>_report_lines``
        methods: {'invoice_rows': [...], 'product_totals': {...},
        'payment_totals': {...}}. ``payment_totals`` is pre-seeded with
        every payment method configured in the system, so it also defines
        the full set of payment-method columns/rows even for methods with
        no activity in the period.
        """
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(label[:31])

        title_format = workbook.add_format({'bold': True, 'font_size': 14})
        section_format = workbook.add_format(
            {'bold': True, 'font_size': 12, 'bg_color': '#305496', 'font_color': 'white'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        divider_format = workbook.add_format({'bg_color': '#000000'})

        payment_methods = sorted(report_data['payment_totals'].keys())
        num_cols = max(4 + len(payment_methods), 2)

        sheet.write(0, 0, _('%s - Daily Sales Report') % label, title_format)

        row = self._write_invoice_details_section(
            sheet, 2, report_data['invoice_rows'], payment_methods,
            section_format, header_format, date_format, money_format)
        row = self._write_section_divider(sheet, row, num_cols, divider_format)

        row = self._write_products_section(
            sheet, row, report_data['product_totals'], section_format, header_format)
        row = self._write_section_divider(sheet, row, num_cols, divider_format)

        self._write_payment_totals_section(
            sheet, row, report_data['payment_totals'], section_format, header_format, money_format)

        widths = [18, 24, 20, 14] + [16] * len(payment_methods)
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)

        workbook.close()
        return output.getvalue()

    @staticmethod
    def _write_section_divider(sheet, row, num_cols, divider_format):
        """Write a solid divider bar across ``num_cols``, one blank row
        below ``row``, with a blank row of spacing on each side. Returns
        the next free row."""
        divider_row = row + 1
        for col in range(num_cols):
            sheet.write_blank(divider_row, col, None, divider_format)
        return divider_row + 2

    @staticmethod
    def _write_invoice_details_section(sheet, row, invoice_rows, payment_methods,
                                        section_format, header_format, date_format, money_format):
        sheet.write(row, 0, _('1. Invoice Details'), section_format)
        row += 1

        headers = [_('Order Ref'), _('Customer'), _('Date/Time'), _('Amount Total')] + payment_methods
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_format)
        row += 1

        for data_row in invoice_rows:
            sheet.write(row, 0, data_row.get('order_ref') or '')
            sheet.write(row, 1, data_row.get('customer') or '')
            order_date = data_row.get('date')
            if order_date:
                sheet.write_datetime(row, 2, order_date, date_format)
            else:
                sheet.write(row, 2, '')
            sheet.write(row, 3, data_row.get('amount_total') or 0.0, money_format)
            payments = data_row.get('payments') or {}
            for col, method in enumerate(payment_methods, start=4):
                amount = payments.get(method)
                sheet.write(row, col, amount if amount else '', money_format)
            row += 1

        return row

    @staticmethod
    def _write_products_section(sheet, row, product_totals, section_format, header_format):
        sheet.write(row, 0, _('2. Products Sold'), section_format)
        row += 1

        sheet.write(row, 0, _('Product'), header_format)
        sheet.write(row, 1, _('Qty'), header_format)
        row += 1

        for product, qty in sorted(product_totals.items(), key=lambda item: item[1], reverse=True):
            sheet.write(row, 0, product)
            sheet.write(row, 1, qty)
            row += 1

        return row

    @staticmethod
    def _write_payment_totals_section(sheet, row, payment_totals, section_format, header_format, money_format):
        sheet.write(row, 0, _('3. Payment Totals'), section_format)
        row += 1

        sheet.write(row, 0, _('Payment Method'), header_format)
        sheet.write(row, 1, _('Total Amount'), header_format)
        row += 1

        for method, amount in sorted(payment_totals.items(), key=lambda item: item[1], reverse=True):
            sheet.write(row, 0, method)
            sheet.write(row, 1, amount, money_format)
            row += 1

        return row

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
        """Return (report_data, order_count, amount_total) for POS orders in
        the period. report_data has 'invoice_rows' (one per order, with a
        per-payment-method breakdown), 'product_totals' (qty sold per
        product) and 'payment_totals' (amount collected per method)."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['pos.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ('paid', 'done', 'invoiced')),
        ])

        invoice_rows = []
        product_totals = {}
        payment_totals = {name: 0.0 for name in self._get_all_pos_payment_method_names()}
        for order in orders:
            payments = self._get_pos_order_payments(order)
            for method, amount in payments.items():
                payment_totals[method] = payment_totals.get(method, 0.0) + amount
            invoice_rows.append({
                'order_ref': order.pos_reference or order.name,
                'customer': order.partner_id.name or '',
                'amount_total': order.amount_total,
                'date': order.date_order,
                'payments': payments,
            })
            for line in order.lines:
                key = line.product_id.display_name
                product_totals[key] = product_totals.get(key, 0.0) + line.qty

        report_data = {
            'invoice_rows': invoice_rows,
            'product_totals': product_totals,
            'payment_totals': payment_totals,
        }
        return report_data, len(orders), sum(orders.mapped('amount_total'))

    def _get_sales_report_lines(self, date_from, date_to):
        """Return (report_data, order_count, amount_total) for confirmed
        Sales orders (excluding website/eCommerce orders) in the period."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['sale.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', '=', 'sale'),
            ('website_id', '=', False),
        ])
        report_data = self._get_sale_order_report_data(orders)
        return report_data, len(orders), sum(orders.mapped('amount_total'))

    def _get_ecommerce_report_lines(self, date_from, date_to):
        """Return (report_data, order_count, amount_total) for confirmed
        website (eCommerce) Sales orders in the period."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds(date_from, date_to)
        orders = self.env['sale.order'].sudo().search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', '=', 'sale'),
            ('website_id', '!=', False),
        ])
        report_data = self._get_sale_order_report_data(orders)
        return report_data, len(orders), sum(orders.mapped('amount_total'))

    def _get_all_pos_payment_method_names(self):
        """Return every POS payment method configured in the system, so
        the report always shows a column/row for each even if it saw no
        activity in the period."""
        return self.env['pos.payment.method'].sudo().search([]).mapped('name')

    @staticmethod
    def _get_pos_order_payments(order):
        """Return {payment_method_name: amount} for a POS order, straight
        from its pos.payment lines."""
        payments = {}
        for payment in order.payment_ids:
            method = payment.payment_method_id.name or _('Unknown')
            payments[method] = payments.get(method, 0.0) + payment.amount
        return payments

    def _get_all_sale_payment_method_names(self):
        """Return every payment method that could apply to a Sales/
        eCommerce order: online payment providers (used at checkout) and
        inbound payment method lines (used when registering a manual
        payment on an invoice)."""
        providers = self.env['payment.provider'].sudo().search([]).mapped('name')
        method_lines = self.env['account.payment.method.line'].sudo().search([
            ('payment_type', '=', 'inbound'),
        ]).mapped('name')
        return list(dict.fromkeys(providers + method_lines))

    def _get_sale_order_report_data(self, orders):
        """Build the invoice/product/payment breakdown for a set of
        sale.order records (used for both Sales and eCommerce reports)."""
        invoice_rows = []
        product_totals = {}
        payment_totals = {name: 0.0 for name in self._get_all_sale_payment_method_names()}
        for order in orders:
            payments = self._get_sale_order_payments(order)
            for method, amount in payments.items():
                payment_totals[method] = payment_totals.get(method, 0.0) + amount
            invoice_rows.append({
                'order_ref': order.name,
                'customer': order.partner_id.name or '',
                'amount_total': order.amount_total,
                'date': order.date_order,
                'payments': payments,
            })
            for line in order.order_line.filtered(lambda l: not l.display_type):
                key = line.product_id.display_name
                product_totals[key] = product_totals.get(key, 0.0) + line.product_uom_qty

        return {
            'invoice_rows': invoice_rows,
            'product_totals': product_totals,
            'payment_totals': payment_totals,
        }

    def _get_sale_order_payments(self, order):
        """Return {payment_method_name: amount} for a sale.order.

        Payment method is resolved in order of preference:
        1. Online payment transactions linked to the order (eCommerce
           checkout), grouped by payment provider name.
        2. Payments reconciled against the order's posted invoices,
           grouped by the payment method / journal used to record them.
        3. If neither is found, the full order amount is bucketed under
           ``UNPAID_METHOD_LABEL`` so the breakdown still adds up to the
           order total.
        """
        transactions = order.transaction_ids.filtered(lambda t: t.state == 'done')
        if transactions:
            payments = {}
            for tx in transactions:
                method = tx.provider_id.name or _('Unknown')
                payments[method] = payments.get(method, 0.0) + tx.amount
            return payments

        payments = {}
        invoices = order.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type == 'out_invoice')
        receivable_lines = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        for partial in receivable_lines.matched_credit_ids:
            reconcile_payment = partial.credit_move_id.move_id.payment_id
            if not reconcile_payment:
                continue
            method = (reconcile_payment.payment_method_line_id.name
                      or reconcile_payment.journal_id.name or _('Unknown'))
            payments[method] = payments.get(method, 0.0) + partial.amount

        if payments:
            return payments
        return {UNPAID_METHOD_LABEL: order.amount_total}
