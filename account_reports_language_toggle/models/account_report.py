# -*- coding: utf-8 -*-
from odoo import models


class AccountReport(models.Model):
    _inherit = 'account.report'

    def dispatch_report_action(self, options, action, action_param=None, on_sections_source=False):
        """Render PDF/XLSX exports in the language chosen via the report's
        language filter (see AccountReportLanguageToggleFilters), instead of
        the requesting user's own language.

        Every other dispatched action (line expansion, column formatting,
        etc.) is left untouched — only exports read ``report_lang``.
        """
        report_lang = options.get('report_lang')
        if report_lang and action in ('export_to_pdf', 'export_to_xlsx'):
            self = self.with_context(lang=report_lang)
        return super(AccountReport, self).dispatch_report_action(
            options, action, action_param=action_param, on_sections_source=on_sections_source,
        )


class AccountGenericTaxReportHandler(models.AbstractModel):
    _inherit = 'account.generic.tax.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options['report_lang'] = previous_options.get('report_lang') or self.env.lang
        options['custom_display_config'].setdefault('components', {})[
            'AccountReportFilters'
        ] = 'AccountReportLanguageToggleFilters'


class AccountPartnerLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options['report_lang'] = previous_options.get('report_lang') or self.env.lang
        options['custom_display_config'].setdefault('components', {})[
            'AccountReportFilters'
        ] = 'AccountReportLanguageToggleFilters'
