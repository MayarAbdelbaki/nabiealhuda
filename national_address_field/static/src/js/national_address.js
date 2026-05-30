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
});
