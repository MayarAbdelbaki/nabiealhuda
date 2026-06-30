import { patch } from "@web/core/utils/patch";
import { CustomerAddress } from "@portal/interactions/address";

/** * Show/hide the Saudi National Address field on the portal (/my/account) and
 * eCommerce (/shop/address) address forms based on the selected country.
 *
 * Odoo 19 drives both forms with the same `CustomerAddress` public interaction
 * (registered as `portal.customer_address`), so patching its country-change
 * hook covers both pages. The field is visible only when the selected
 * country's ISO code is "SA".*/
patch(CustomerAddress.prototype, {
    /**
     * @override
     * Runs on initial load (via willStart) and on every country change.
     */
    async _onChangeCountry(init = false) {
        await super._onChangeCountry(init);
        this._toggleNationalAddress();
    },

    /**
     * Toggle the national address field: shown only for Saudi Arabia ("SA").
     */
    _toggleNationalAddress() {
        const input = this.addressForm?.x_national_address;
        if (!input) {
            // Field not rendered on this form — nothing to do.
            return;
        }

        const isSaudiArabia = this._getSelectedCountryCode().toUpperCase() === "SA";
        // The wrapping div carries the label + input.
        input.parentElement.style.display = isSaudiArabia ? "" : "none";

        if (!isSaudiArabia) {
            // Clear the value when hidden so a stale national address is not
            // saved for a non-Saudi country.
            input.value = "";
        }
    },

    /**
     * @override
     * Null-safe: we removed the Street/Zip inputs from the form, but core
     * `_onChangeCountry` references them unconditionally (to reorder zip/city
     * and to show/hide street/zip/city). When the input is missing we return a
     * stub whose `.after()`/`.before()` are no-ops, so the reorder is skipped
     * and City keeps the position set in the template.
     */
    _getInputDiv(name) {
        const input = this.addressForm[name];
        if (input) {
            return input.parentElement;
        }
        return { after() {}, before() {}, style: {} };
    },

    /** @override Null-safe: ignore fields that are not on the form. */
    _showInput(name) {
        const input = this.addressForm[name];
        if (input) {
            input.parentElement.style.display = "";
        }
    },

    /** @override Null-safe: ignore fields that are not on the form. */
    _hideInput(name) {
        const input = this.addressForm[name];
        if (input) {
            input.parentElement.style.display = "none";
        }
    },

    /** @override Null-safe: ignore fields that are not on the form. */
    _markRequired(name, required) {
        const input = this.addressForm[name];
        if (input) {
            input.required = required;
        }
        this._getInputLabel(name)?.classList.toggle("label-optional", !required);
    },
});
