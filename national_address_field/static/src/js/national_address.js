import { patch } from "@web/core/utils/patch";
import { CustomerAddress } from "@portal/interactions/address";

// Fields we keep in the DOM but hide (see national_address.scss). They must not
// drive Odoo's core address reorder logic: `_onChangeCountry` moves the City
// div next to the (hidden) Zip div on every country change, which would undo
// the field order set in the template. Returning a stub div for these makes
// that reorder a no-op.
const HIDDEN_ADDRESS_FIELDS = new Set(["street", "street2", "zip"]);

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
        if (init) {
            this._initKsaCityCascade();
        }
    },

    /**
     * Wire the "الحي" city <select> (see views/portal_templates.xml) to
     * only list cities belonging to the region currently picked in
     * "المدينة" (state_id), using the dataset embedded server-side by
     * controllers/main.py. Runs once, on interaction setup.
     */
    _initKsaCityCascade() {
        const citySelect = this.addressForm?.city;
        const stateSelect = this.addressForm?.state_id;
        const dataEl = document.getElementById("o_ksa_cities_data");
        if (!citySelect || citySelect.tagName !== "SELECT" || !stateSelect || !dataEl) {
            // City is still a plain text input, or the field/dataset isn't
            // rendered on this form — nothing to wire up.
            return;
        }
        try {
            this._ksaCitiesByState = JSON.parse(dataEl.value);
        } catch {
            return;
        }
        this._ksaCitySelect = citySelect;
        stateSelect.addEventListener("change", () => this._refreshKsaCityOptions());
        this._refreshKsaCityOptions();
    },

    /**
     * Rebuild the city <select>'s options for the currently selected
     * region, keeping the current value selected if it's still valid.
     */
    _refreshKsaCityOptions() {
        const citySelect = this._ksaCitySelect;
        const stateSelect = this.addressForm?.state_id;
        if (!citySelect || !stateSelect) {
            return;
        }
        const currentValue = citySelect.value;
        const cities = this._ksaCitiesByState[stateSelect.value] || [];

        citySelect.replaceChildren();
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "اختر الحي...";
        citySelect.appendChild(placeholder);

        let matched = false;
        for (const name of cities) {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            if (name === currentValue) {
                option.selected = true;
                matched = true;
            }
            citySelect.appendChild(option);
        }
        if (!matched) {
            citySelect.value = "";
        }
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
        if (!input || HIDDEN_ADDRESS_FIELDS.has(name)) {
            // Missing or hidden field: return a stub whose reorder methods are
            // no-ops so core `_onChangeCountry` neither crashes nor moves City.
            return { after() {}, before() {}, style: {} };
        }
        return input.parentElement;
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
