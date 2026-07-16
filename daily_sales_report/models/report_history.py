# -*- coding: utf-8 -*-
from odoo import fields, models


class DailySalesReportHistory(models.Model):
    """Read-only log of every report send attempt (successful or failed)."""
    _name = 'daily.sales.report.history'
    _description = 'Daily Sales Report History'
    _order = 'sent_date desc'

    config_id = fields.Many2one(
        'daily.sales.report.config', string='Report Configuration',
        required=True, ondelete='cascade', index=True)
    sent_date = fields.Datetime(required=True, default=fields.Datetime.now)
    date_from = fields.Date(string='Period From')
    date_to = fields.Date(string='Period To')
    periodicity = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Periodicity')
    recipients = fields.Char(string='Recipients', help='Snapshot of the recipient emails at send time')

    pos_orders_count = fields.Integer(string='POS Orders')
    sales_orders_count = fields.Integer(string='Sales Orders')
    ecommerce_orders_count = fields.Integer(string='eCommerce Orders')

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id.id)
    pos_total = fields.Monetary(string='POS Total', currency_field='currency_id')
    sales_total = fields.Monetary(string='Sales Total', currency_field='currency_id')
    ecommerce_total = fields.Monetary(string='eCommerce Total', currency_field='currency_id')

    attachment_ids = fields.Many2many(
        'ir.attachment', string='Report Files',
        help='The XLSX files that were generated and sent for this run')

    status = fields.Selection([
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], string='Status', default='sent', required=True)
    error_message = fields.Text(string='Error Message')
