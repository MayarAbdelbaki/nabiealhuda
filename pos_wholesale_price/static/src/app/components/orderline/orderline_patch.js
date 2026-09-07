import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    get infoListClasses() {
        const classes = super.infoListClasses;
        if (classes) {
            return classes;
        }
        if (this.props.mode !== "receipt" && this.line.is_wholesale) {
            return "gap-2 mt-1";
        }
        return classes;
    },
});
