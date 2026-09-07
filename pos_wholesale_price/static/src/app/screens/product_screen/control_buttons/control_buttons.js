import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";

patch(ControlButtons.prototype, {
    get wholesaleOrderline() {
        return this.currentOrder?.getSelectedOrderline();
    },

    displayWholesaleBtn() {
        return Boolean(this.wholesaleOrderline);
    },

    async clickWholesalePrice() {
        const line = this.wholesaleOrderline;
        if (!line) {
            return;
        }
        const result = line.toggleWholesalePrice();
        if (result !== true) {
            this.dialog.add(AlertDialog, result);
        }
    },
});
