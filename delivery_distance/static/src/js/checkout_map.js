import { patch } from "@web/core/utils/patch";
import { loadJS, loadCSS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { CustomerAddress } from "@portal/interactions/address";

const LEAFLET_VERSION = "1.9.4";
const LEAFLET_CDN = "https://unpkg.com/leaflet@" + LEAFLET_VERSION + "/dist";
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
const NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse";
// Default map center when the address has no coordinates yet (Riyadh, SA).
const DEFAULT_CENTER = [24.7136, 46.6753];
// Countries delivery is available to (ISO 3166-1 alpha-2). Keep this in sync
// with ALLOWED_COUNTRY_CODES in controllers/main.py.
const ALLOWED_COUNTRY_CODES = [
    "SA", "AE", "KW", "QA", "BH", "OM", "EG", "SD",
];
const COUNTRY_NOT_ALLOWED_MSG = "التوصيل غير متاح لهذا البلد";

/**
 * Add an interactive OpenStreetMap location picker to the portal
 * (/my/account) and eCommerce (/shop/address) address forms. Picking a point
 * fills the required `partner_latitude` / `partner_longitude` inputs so the
 * distance-based delivery method can price the order. Free, no API key.
 */
patch(CustomerAddress.prototype, {
    setup() {
        super.setup();
        this._deliveryMap = null;
        this._deliveryMarker = null;
        // Guard against the reverse <-> forward geocode feedback loop.
        this._syncing = false;
        this._geocodeTimer = null;
        // ISO country code <-> Odoo country id maps (language-independent
        // matching, so "Egypt"/"مصر" resolve to the same record).
        this._countryCodeToId = null;
        this._countryIdToCode = null;
        // Country code / city of the current map pin, to verify the typed
        // address matches the location before submitting.
        this._pinCountryCode = null;
        this._pinCity = null;
        // Kick off the map once the form is in the DOM.
        this._initDeliveryMap();
    },

    get _latInput() {
        return this.addressForm?.partner_latitude;
    },

    get _lngInput() {
        return this.addressForm?.partner_longitude;
    },

    async _initDeliveryMap() {
        const container = this.el.querySelector("#delivery_location_map");
        if (!container || !this._latInput || !this._lngInput) {
            // Map not rendered on this form — nothing to do.
            return;
        }
        await loadCSS(LEAFLET_CDN + "/leaflet.css");
        await loadJS(LEAFLET_CDN + "/leaflet.js");
        const L = window.L;
        if (!L) {
            return;
        }
        delete L.Icon.Default.prototype._getIconUrl;
        L.Icon.Default.mergeOptions({
            iconRetinaUrl: LEAFLET_CDN + "/images/marker-icon-2x.png",
            iconUrl: LEAFLET_CDN + "/images/marker-icon.png",
            shadowUrl: LEAFLET_CDN + "/images/marker-shadow.png",
        });

        const lat = parseFloat(this._latInput.value);
        const lng = parseFloat(this._lngInput.value);
        const hasCoords = !isNaN(lat) && !isNaN(lng) && (lat || lng);
        const center = hasCoords ? [lat, lng] : DEFAULT_CENTER;

        this._deliveryMap = L.map(container).setView(center, hasCoords ? 15 : 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "© OpenStreetMap contributors",
        }).addTo(this._deliveryMap);

        this._deliveryMarker = L.marker(center, { draggable: true }).addTo(
            this._deliveryMap
        );
        this._deliveryMarker.on("dragend", (ev) => {
            const pos = ev.target.getLatLng();
            this._setCoords(pos.lat, pos.lng);
        });
        this._deliveryMap.on("click", (ev) => {
            this._deliveryMarker.setLatLng(ev.latlng);
            this._setCoords(ev.latlng.lat, ev.latlng.lng);
        });

        // The container may be sized after render; recompute once visible.
        setTimeout(() => this._deliveryMap && this._deliveryMap.invalidateSize(), 200);

        await this._loadCountryCodes();
        this._restrictCountryDropdown();
        this._bindDeliverySearch();
        this._bindLocationValidation();
        this._bindAddressFields();
    },

    /**
     * Load the ISO-code <-> id mapping for countries so matching does not
     * depend on the translated label. Degrades gracefully to name matching.
     */
    async _loadCountryCodes() {
        try {
            const countries = await rpc("/web/dataset/call_kw", {
                model: "res.country",
                method: "search_read",
                args: [[], ["id", "code"]],
                kwargs: {},
            });
            this._countryCodeToId = {};
            this._countryIdToCode = {};
            for (const country of countries) {
                if (country.code) {
                    const code = country.code.toUpperCase();
                    this._countryCodeToId[code] = country.id;
                    this._countryIdToCode[String(country.id)] = code;
                }
            }
        } catch (error) {
            // Public read may be denied: fall back to label matching.
            this._countryCodeToId = null;
            this._countryIdToCode = null;
        }
    },

    _isAllowedCountryCode(code) {
        return !!code && ALLOWED_COUNTRY_CODES.includes(code.toUpperCase());
    },

    /**
     * Remove countries outside the delivery area from the dropdown so the
     * customer cannot pick them. Resets the selection if it became invalid.
     */
    _restrictCountryDropdown() {
        const select = this.addressForm?.country_id;
        if (!select || !this._countryIdToCode) {
            return;
        }
        for (const option of Array.from(select.options)) {
            if (!option.value) {
                continue; // keep the empty placeholder
            }
            const code = this._countryIdToCode[option.value];
            if (code && !this._isAllowedCountryCode(code)) {
                option.remove();
            }
        }
        const currentCode =
            select.value && this._countryIdToCode[select.value];
        if (currentCode && !this._isAllowedCountryCode(currentCode)) {
            select.value = "";
            select.dispatchEvent(new Event("change", { bubbles: true }));
        }
    },

    /**
     * Move the map when the customer edits the country / state / city / zip /
     * street fields (forward geocoding), so the two stay in sync.
     */
    _bindAddressFields() {
        const form = this.addressForm;
        const fields = [
            form.country_id,
            form.state_id,
            form.city,
            form.zip,
            form.street,
        ];
        for (const field of fields) {
            if (field) {
                field.addEventListener("change", () =>
                    this._scheduleGeocodeFromFields()
                );
            }
        }
    },

    _scheduleGeocodeFromFields() {
        // Ignore changes we made ourselves while reverse-geocoding.
        if (this._syncing) {
            return;
        }
        clearTimeout(this._geocodeTimer);
        this._geocodeTimer = setTimeout(
            () => this._geocodeFromFields(),
            500
        );
    },

    async _geocodeFromFields() {
        if (this._syncing || !this._deliveryMap) {
            return;
        }
        const form = this.addressForm;
        const query = [
            form.street ? form.street.value.trim() : "",
            form.city ? form.city.value.trim() : "",
            this._selectedText(form.state_id),
            form.zip ? form.zip.value.trim() : "",
            this._selectedText(form.country_id),
        ]
            .filter(Boolean)
            .join(", ");
        if (!query) {
            return;
        }
        let result;
        try {
            let url =
                NOMINATIM_URL +
                "?format=jsonv2&limit=1&q=" +
                encodeURIComponent(query);
            // Restrict to the selected country by ISO code (language-safe),
            // so "مصر"/"Egypt" both bias the search to Egypt.
            const countryId = form.country_id ? form.country_id.value : "";
            const code =
                this._countryIdToCode && this._countryIdToCode[countryId];
            if (code) {
                url += "&countrycodes=" + code.toLowerCase();
            }
            const response = await fetch(url, {
                headers: { Accept: "application/json" },
            });
            const data = await response.json();
            result = data && data[0];
        } catch (error) {
            return;
        }
        if (!result) {
            return;
        }
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);
        this._deliveryMap.setView([lat, lng], 15);
        this._deliveryMarker.setLatLng([lat, lng]);
        // The pin now matches the typed country/city: record it so the
        // submit-time consistency check passes.
        const countryId = form.country_id ? form.country_id.value : "";
        this._pinCountryCode =
            (this._countryIdToCode && this._countryIdToCode[countryId]) ||
            this._pinCountryCode;
        this._pinCity = form.city ? form.city.value.trim() : this._pinCity;
        // Fields already hold what the user typed; don't reverse back onto them.
        this._setCoords(lat, lng, false);
    },

    _selectedText(select) {
        if (!select || select.selectedIndex < 0) {
            return "";
        }
        const option = select.options[select.selectedIndex];
        return option ? option.textContent.trim() : "";
    },

    /**
     * Block submitting the address form until a location is picked.
     * Runs in the capture phase and stops propagation so Odoo's own submit
     * handler does not fire when the location is missing.
     */
    _bindLocationValidation() {
        this.addressForm.addEventListener(
            "submit",
            (ev) => {
                let message = null;
                if (!this._hasLocation()) {
                    message = "حدد موقعك على الخريطة";
                } else {
                    message = this._checkAddressMatchesPin();
                }
                if (message) {
                    ev.preventDefault();
                    ev.stopImmediatePropagation();
                    this._showLocationError(message);
                } else {
                    this._clearLocationError();
                }
            },
            { capture: true }
        );
    },

    /**
     * Verify the typed address matches the map pin. Only the country is
     * checked (by ISO code). Returns an error message on mismatch, else null.
     */
    _checkAddressMatchesPin() {
        const form = this.addressForm;
        // Outside the delivery area: block (pin or selected country).
        if (
            this._pinCountryCode &&
            !this._isAllowedCountryCode(this._pinCountryCode)
        ) {
            return COUNTRY_NOT_ALLOWED_MSG;
        }
        if (this._countryIdToCode && form.country_id && form.country_id.value) {
            const selected = this._countryIdToCode[form.country_id.value];
            if (selected && !this._isAllowedCountryCode(selected)) {
                return COUNTRY_NOT_ALLOWED_MSG;
            }
        }
        // Country: language-independent ISO code comparison.
        if (
            this._pinCountryCode &&
            this._countryIdToCode &&
            form.country_id &&
            form.country_id.value
        ) {
            const selected = this._countryIdToCode[form.country_id.value];
            if (selected && selected !== this._pinCountryCode) {
                return "الدولة المختارة لا تطابق موقعك على الخريطة. صحّح الدولة أو حرّك الدبوس.";
            }
        }
        return null;
    },

    _hasLocation() {
        const lat = parseFloat(this._latInput && this._latInput.value);
        const lng = parseFloat(this._lngInput && this._lngInput.value);
        return !isNaN(lat) && !isNaN(lng) && (lat !== 0 || lng !== 0);
    },

    _showLocationError(message = "حدد موقعك على الخريطة") {
        const container = this.el.querySelector("#div_delivery_location");
        if (!container) {
            return;
        }
        let alertEl = container.querySelector(".o_delivery_location_error");
        if (!alertEl) {
            alertEl = document.createElement("div");
            alertEl.className =
                "o_delivery_location_error alert alert-danger mt-2 mb-0";
            alertEl.setAttribute("role", "alert");
            container.appendChild(alertEl);
        }
        alertEl.textContent = message;
        alertEl.scrollIntoView({ behavior: "smooth", block: "center" });
    },

    _clearLocationError() {
        const alertEl = this.el.querySelector(".o_delivery_location_error");
        if (alertEl) {
            alertEl.remove();
        }
    },

    _bindDeliverySearch() {
        const input = this.el.querySelector("#delivery_location_search");
        const button = this.el.querySelector("#delivery_location_search_btn");
        if (button) {
            button.addEventListener("click", () => this._searchDeliveryAddress());
        }
        if (input) {
            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") {
                    ev.preventDefault();
                    this._searchDeliveryAddress();
                }
            });
        }
        const pinButton = this.el.querySelector("#delivery_location_pin_me");
        if (pinButton) {
            pinButton.addEventListener("click", () => this._pinMyLocation());
        }
    },

    /**
     * Center the map on the visitor's current GPS position (browser
     * Geolocation API) and drop the pin there. Requires HTTPS or localhost.
     */
    _pinMyLocation() {
        if (!navigator.geolocation) {
            this._showLocationError("المتصفح لا يدعم تحديد الموقع.");
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                if (this._deliveryMap && this._deliveryMarker) {
                    this._deliveryMap.setView([lat, lng], 16);
                    this._deliveryMarker.setLatLng([lat, lng]);
                }
                // Reverse-geocode to fill country/city and run the area check.
                this._setCoords(lat, lng);
            },
            () => {
                this._showLocationError(
                    "تعذّر تحديد موقعك الحالي. تأكد من السماح بالوصول للموقع."
                );
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },

    async _searchDeliveryAddress() {
        const input = this.el.querySelector("#delivery_location_search");
        const resultsEl = this.el.querySelector("#delivery_location_results");
        if (!input || !resultsEl) {
            return;
        }
        const query = input.value.trim();
        resultsEl.innerHTML = "";
        if (!query) {
            return;
        }
        let data = [];
        try {
            const url =
                NOMINATIM_URL +
                "?format=jsonv2&limit=5&q=" +
                encodeURIComponent(query);
            const response = await fetch(url, {
                headers: { Accept: "application/json" },
            });
            data = await response.json();
        } catch (error) {
            return;
        }
        for (const item of data) {
            const button = document.createElement("button");
            button.type = "button";
            button.className =
                "list-group-item list-group-item-action text-truncate";
            button.textContent = item.display_name;
            button.addEventListener("click", () => {
                const lat = parseFloat(item.lat);
                const lng = parseFloat(item.lon);
                this._deliveryMap.setView([lat, lng], 16);
                this._deliveryMarker.setLatLng([lat, lng]);
                this._setCoords(lat, lng);
                resultsEl.innerHTML = "";
                input.value = item.display_name;
            });
            resultsEl.appendChild(button);
        }
    },

    _setCoords(lat, lng, doReverse = true) {
        // Round to a sane precision and fire `input` so validation clears.
        this._latInput.value = lat.toFixed(7);
        this._lngInput.value = lng.toFixed(7);
        this._latInput.dispatchEvent(new Event("input", { bubbles: true }));
        this._lngInput.dispatchEvent(new Event("input", { bubbles: true }));
        this._clearLocationError();
        if (doReverse) {
            // Auto-fill country / state / city / zip / street from the point.
            this._reverseGeocode(lat, lng);
        }
    },

    /**
     * Reverse-geocode the picked point and fill the address fields.
     * Best effort: country/state selects are matched by their visible label.
     */
    async _reverseGeocode(lat, lng) {
        let address;
        try {
            const lang = document.documentElement.lang || "en";
            const url =
                NOMINATIM_REVERSE_URL +
                "?format=jsonv2&addressdetails=1&accept-language=" +
                encodeURIComponent(lang) +
                "&lat=" +
                encodeURIComponent(lat) +
                "&lon=" +
                encodeURIComponent(lng);
            const response = await fetch(url, {
                headers: { Accept: "application/json" },
            });
            const data = await response.json();
            address = data.address;
        } catch (error) {
            return;
        }
        if (!address) {
            return;
        }

        const form = this.addressForm;
        const city =
            address.city ||
            address.town ||
            address.village ||
            address.municipality ||
            address.suburb ||
            address.county;
        const street = [address.road, address.house_number]
            .filter(Boolean)
            .join(" ");

        // Remember what the pin resolves to, for the submit-time check.
        const pinCode = (address.country_code || "").toUpperCase();
        this._pinCountryCode = pinCode || null;
        this._pinCity = city || null;

        // Refuse a location outside the delivery area: warn and do not fill
        // the address fields (the submit check keeps the form blocked too).
        if (pinCode && !this._isAllowedCountryCode(pinCode)) {
            this._showLocationError(
                COUNTRY_NOT_ALLOWED_MSG +
                    (address.country ? " (" + address.country + ")" : "")
            );
            return;
        }

        // Suppress the field-change listener while we fill the form, otherwise
        // updating the fields would trigger a forward geocode back onto the map.
        this._syncing = true;

        const applyTextFields = () => {
            this._fillInput(form.street, street);
            this._fillInput(form.city, city);
            this._fillInput(form.zip, address.postcode);
            if (address.state) {
                this._selectByLabel(form.state_id, address.state);
            } else if (address.state_district) {
                this._selectByLabel(form.state_id, address.state_district);
            }
            this._syncing = false;
        };

        // Set the country first: changing it reloads the state list and may
        // re-render dependent fields, so fill the rest once that settled.
        if (this._setCountryFromAddress(form, address)) {
            setTimeout(applyTextFields, 700);
        } else {
            applyTextFields();
        }
    },

    /**
     * Select the country from the reverse-geocode result. Prefers the ISO
     * code (language-independent) and falls back to matching the label.
     * Returns true when the selected country actually changed.
     */
    _setCountryFromAddress(form, address) {
        if (!form.country_id) {
            return false;
        }
        if (this._countryCodeToId && address.country_code) {
            const id = this._countryCodeToId[address.country_code.toUpperCase()];
            if (id) {
                const value = String(id);
                if (form.country_id.value === value) {
                    return false;
                }
                form.country_id.value = value;
                form.country_id.dispatchEvent(
                    new Event("change", { bubbles: true })
                );
                return true;
            }
        }
        // No code map (or unknown code): match by translated label.
        return address.country
            ? this._selectByLabel(form.country_id, address.country)
            : false;
    },

    _fillInput(input, value) {
        if (input && value) {
            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        }
    },

    /**
     * Select the <option> whose visible label best matches `text`.
     * Returns true when the selection actually changed.
     */
    _selectByLabel(select, text) {
        if (!select || !select.options || !text) {
            return false;
        }
        const wanted = text.trim().toLowerCase();
        let match = null;
        for (const option of select.options) {
            const label = option.textContent.trim().toLowerCase();
            if (!label) {
                continue;
            }
            if (label === wanted) {
                match = option;
                break;
            }
            // Fall back to a contains match (guard against tiny labels).
            if (
                !match &&
                label.length > 2 &&
                (label.includes(wanted) || wanted.includes(label))
            ) {
                match = option;
            }
        }
        if (match && select.value !== match.value) {
            select.value = match.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
        }
        return false;
    },
});
