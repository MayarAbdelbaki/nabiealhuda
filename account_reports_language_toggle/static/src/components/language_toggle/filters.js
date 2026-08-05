/** @odoo-module **/

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

// Language names shown natively (not translated to the current UI
// language), same convention as Odoo's own language selectors.
const REPORT_LANGUAGES = {
    en_US: "English",
    ar_001: "العربية",
};

export class AccountReportLanguageToggleFilters extends AccountReportFilters {
    static template = "account_reports_language_toggle.Filters";

    get reportLanguageName() {
        const lang = this.controller.cachedFilterOptions.report_lang;
        return REPORT_LANGUAGES[lang] || lang;
    }

    get reportLanguages() {
        return Object.entries(REPORT_LANGUAGES).map(([value, name]) => ({ value, name }));
    }

    async filterReportLanguage(lang) {
        await this.controller.updateOption("report_lang", lang, false);
        this.controller.saveSessionOptions(this.controller.cachedFilterOptions);
    }
}

AccountReport.registerCustomComponent(AccountReportLanguageToggleFilters);
