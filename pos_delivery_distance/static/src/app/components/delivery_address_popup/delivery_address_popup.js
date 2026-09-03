import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { Input } from "@point_of_sale/app/components/inputs/input/input";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Collects a delivery address for the POS 'Delivery' button: either a starting
 * point taken from the customer's own address / a previously picked delivery
 * address (``props.address``), or a blank form. It only gathers and validates
 * the field values -- creating/reusing the child contact and rating it happen
 * in ControlButtons after this dialog resolves.
 */
export class DeliveryAddressPopup extends Component {
    static template = "pos_delivery_distance.DeliveryAddressPopup";
    static components = { Dialog, Input };
    static props = {
        partner: Object,
        address: { type: [Object, Boolean], optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        address: false,
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");

        const source = this.props.address || this.props.partner;
        const country = source.country_id || this.pos.company.country_id;
        const state = source.state_id;
        this.state = useState({
            street: source.street || "",
            street2: source.street2 || "",
            city: source.city || "",
            zip: source.zip || "",
            phone: source.phone || "",
            nationalAddress: this.props.address?.x_national_address || "",
            countryId: country?.id || false,
            countryName: country?.name || "",
            stateId: state?.id || false,
            stateName: state?.name || "",
        });
    }

    get isValid() {
        return Boolean(this.state.street.trim() && this.state.city.trim() && this.state.countryId);
    }

    get availableStates() {
        const country = this.pos.models["res.country"].get(this.state.countryId);
        return country?.state_ids || [];
    }

    async selectCountry() {
        const countries = this.pos.models["res.country"].getAll();
        const country = await new Promise((resolve) => {
            this.dialog.add(SelectionPopup, {
                title: _t("Select a country"),
                list: [...countries]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((c) => ({
                        id: c.id,
                        label: c.name,
                        isSelected: c.id === this.state.countryId,
                        item: c,
                    })),
                getPayload: resolve,
            });
        });
        if (!country) {
            return;
        }
        this.state.countryId = country.id;
        this.state.countryName = country.name;
        if (this.state.stateId && !country.state_ids.some((s) => s.id === this.state.stateId)) {
            this.state.stateId = false;
            this.state.stateName = "";
        }
    }

    async selectState() {
        const states = this.availableStates;
        if (!states.length) {
            return;
        }
        const state = await new Promise((resolve) => {
            this.dialog.add(SelectionPopup, {
                title: _t("Select a state"),
                list: [...states]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((s) => ({
                        id: s.id,
                        label: s.name,
                        isSelected: s.id === this.state.stateId,
                        item: s,
                    })),
                getPayload: resolve,
            });
        });
        if (state) {
            this.state.stateId = state.id;
            this.state.stateName = state.name;
        }
    }

    confirm() {
        if (!this.isValid) {
            return;
        }
        this.props.getPayload({
            street: this.state.street.trim(),
            street2: this.state.street2.trim(),
            city: this.state.city.trim(),
            zip: this.state.zip.trim(),
            phone: this.state.phone.trim(),
            x_national_address: this.state.nationalAddress.trim(),
            country_id: this.state.countryId,
            state_id: this.state.stateId || false,
        });
        this.props.close();
    }
}
