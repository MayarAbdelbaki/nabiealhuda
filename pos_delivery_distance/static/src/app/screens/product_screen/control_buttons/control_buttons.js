import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { DeliveryAddressPopup } from "@pos_delivery_distance/app/components/delivery_address_popup/delivery_address_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";

patch(ControlButtons.prototype, {
    get showDeliveryButton() {
        return Boolean(this.pos.config.delivery_carrier_id && this.pos.config.delivery_product_id);
    },

    async clickDelivery() {
        const order = this.currentOrder;
        const partner = this.partner;
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("No customer"),
                body: _t("Select a customer before adding a delivery address."),
            });
            return;
        }

        const addressVals = await makeAwaitable(this.dialog, DeliveryAddressPopup, {
            partner,
            address: order.partner_shipping_id || false,
        });
        if (!addressVals) {
            return;
        }

        const carrier = this.pos.config.delivery_carrier_id;
        const saved = await this.pos.data.callRelated(
            "res.partner",
            "action_pos_get_delivery_address",
            [this.pos.config.id, partner.id, addressVals]
        );
        const address = saved?.["res.partner"]?.[0];
        if (!address) {
            this.dialog.add(AlertDialog, {
                title: _t("Delivery address"),
                body: _t("Could not save the delivery address."),
            });
            return;
        }

        const rate = await this.pos.data.call("delivery.carrier", "action_pos_rate_delivery", [
            carrier.id,
            address.id,
            this.pos.config.id,
        ]);

        if (!rate.success) {
            this.dialog.add(AlertDialog, {
                title: _t("Delivery pricing"),
                body: rate.error_message || _t("Could not price this delivery address."),
            });
            return;
        }

        order.update({ partner_shipping_id: address });
        order.getDeliveryLine()?.delete();

        const product = this.pos.config.delivery_product_id;
        await this.pos.addLineToCurrentOrder(
            {
                product_id: product,
                product_tmpl_id: product.product_tmpl_id,
                price_unit: rate.price,
                qty: 1,
            },
            { merge: false }
        );

        this.notification.add(
            rate.warning_message ||
                _t("Delivery price: %s", this.env.utils.formatCurrency(rate.price)),
            { type: "success" }
        );
    },
});
