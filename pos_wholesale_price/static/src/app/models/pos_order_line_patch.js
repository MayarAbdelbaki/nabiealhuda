import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrderline.prototype, {
    /**
     * Apply the product's Wholesale Price (and wholesale taxes) on this line.
     * @returns {true|{title: string, body: string}} `true` on success, or an
     *  error payload (suitable for AlertDialog) when no wholesale price is
     *  configured on the product.
     */
    applyWholesalePrice() {
        const product = this.getProduct();
        const wholesalePrice = product.wholesale_price;

        if (!wholesalePrice) {
            return {
                title: _t("لا يوجد سعر جملة"),
                body: _t(
                    "لا يوجد سعر جملة محدد للمنتج '%s'. يرجى تحديد سعر الجملة في بطاقة المنتج أولاً.",
                    product.display_name
                ),
            };
        }

        this.order_id.assertEditable();
        this.is_wholesale = true;
        this.wholesale_price_unit = wholesalePrice;
        this.price_type = "manual";
        this.setUnitPrice(wholesalePrice);
        this.update({
            wholesale_tax_ids: product.wholesale_tax_ids,
            tax_ids: product.wholesale_tax_ids,
        });
        return true;
    },

    /**
     * Restore the normal sales price and taxes on this line.
     */
    removeWholesalePrice() {
        const product = this.getProduct();
        const productTemplate = product.product_tmpl_id;

        this.order_id.assertEditable();
        this.is_wholesale = false;
        this.wholesale_price_unit = 0;
        this.price_type = "original";
        this.setUnitPrice(
            productTemplate.getPrice(
                this.order_id.pricelist_id,
                this.getQuantity(),
                this.getPriceExtra(),
                false,
                product
            )
        );
        this.update({
            wholesale_tax_ids: [],
            tax_ids: product.taxes_id,
        });
        return true;
    },

    /**
     * Toggle the Wholesale Price on this line.
     * @returns {true|{title: string, body: string}}
     */
    toggleWholesalePrice() {
        return this.is_wholesale ? this.removeWholesalePrice() : this.applyWholesalePrice();
    },

    prepareBaseLineForTaxesComputationExtraValues(customValues = {}) {
        const values = super.prepareBaseLineForTaxesComputationExtraValues(customValues);
        // The base implementation always recomputes taxes from the product's
        // normal `taxes_id` whenever a fiscal position is set on the order,
        // ignoring whatever `tax_ids` was set on the line. When this line is
        // wholesale, we need that same fiscal-position remapping to be based
        // on the product's `wholesale_tax_ids` instead.
        if (this.is_wholesale) {
            const wholesaleTaxes = this.getProduct().wholesale_tax_ids || [];
            values.tax_ids = this.order_id.fiscal_position_id
                ? this.order_id.fiscal_position_id.getTaxesAfterFiscalPosition(wholesaleTaxes)
                : wholesaleTaxes;
        }
        return values;
    },
});
