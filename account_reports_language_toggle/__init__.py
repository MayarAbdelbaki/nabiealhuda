from . import models

# Arabic translation of the Saudi VAT Return ("VAT Return (SA)") line labels.
# Odoo's l10n_sa module never shipped an ar_001 translation for these
# specific lines (its i18n_extra/ar.po only covers a different, unused
# "(Base)"/"(Tax)" line set) — without this, the language toggle added by
# this module would translate the report's title/headers but every line
# label would stay in English. Wording follows the terms used on ZATCA's
# own VAT return form.
_LINE_TRANSLATIONS_AR = {
    'l10n_sa.tax_report_line_vat_on_sale': 'المبيعات الخاضعة لضريبة القيمة المضافة:',
    'l10n_sa.tax_report_line_standard_rated_sale': '1. المبيعات الخاضعة للنسبة الأساسية',
    'l10n_sa.tax_report_line_ph_pe_fh': '2. الرعاية الصحية الخاصة / التعليم الخاص / بيع أول منزل للمواطنين',
    'l10n_sa.tax_report_line_zero_rated_domestic_sale': '3. المبيعات المحلية الخاضعة لنسبة الصفر بالمائة',
    'l10n_sa.tax_report_line_exports': '4. الصادرات',
    'l10n_sa.tax_report_line_exempt_sale': '5. المبيعات المعفاة',
    'l10n_sa.tax_report_line_total_sale': '6. إجمالي المبيعات',
    'l10n_sa.tax_report_line_vat_on_purchase': 'المشتريات الخاضعة لضريبة القيمة المضافة:',
    'l10n_sa.tax_report_line_standard_rated_domestic_purchase': '7. المشتريات المحلية الخاضعة للنسبة الأساسية',
    'l10n_sa.tax_report_line_imports_subject_to_vat_paid_at_customs': '8. الواردات الخاضعة لضريبة القيمة المضافة المدفوعة عند الجمارك',
    'l10n_sa.tax_report_line_imports_subject_to_vat_reverse_charge': '9. الواردات الخاضعة لضريبة القيمة المضافة المحتسبة من خلال آلية الاحتساب العكسي',
    'l10n_sa.tax_report_line_zero_rated_purchase': '10. المشتريات الخاضعة لنسبة الصفر بالمائة',
    'l10n_sa.tax_report_line_exempt_purchase': '11. المشتريات المعفاة',
    'l10n_sa.tax_report_line_total_purchase': '12. إجمالي المشتريات',
    'l10n_sa.tax_report_line_total_vat_due_for_current_period': '13. إجمالي ضريبة القيمة المضافة المستحقة للفترة الحالية',
    'l10n_sa.tax_report_line_corrections_from_previous_period': '14. تصحيحات من الفترة السابقة (بين +- 5000 ريال سعودي)',
    'l10n_sa.tax_report_line_vat_credit_carried_forward_from_previous_period': '15. رصيد ضريبة القيمة المضافة المرحل من الفترة السابقة',
    'l10n_sa.tax_report_line_net_vat_due': '16. صافي ضريبة القيمة المضافة المستحقة (أو المطالبة باستردادها)',
}


def post_init_hook(env):
    for xmlid, arabic_name in _LINE_TRANSLATIONS_AR.items():
        line = env.ref(xmlid, raise_if_not_found=False)
        if line:
            line.with_context(lang='ar_001').write({'name': arabic_name})
