import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    getDeliveryLine() {
        const product = this.config.delivery_product_id;
        return product && this.lines?.find((line) => line.product_id.id === product.id);
    },
});
