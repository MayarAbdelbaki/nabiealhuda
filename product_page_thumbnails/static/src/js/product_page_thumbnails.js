/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

// How many thumbnails a single arrow click slides past.
const STEP = 3;

/**
 * Prev/next arrows for the small thumbnail strip on the product page: the
 * track only shows a few thumbnails at a time (see the CSS `max-width` on
 * `.o_product_page_thumbnails_track`) and arrows slide through the rest,
 * instead of showing every thumbnail at once.
 *
 * Scrolls by calling `scrollIntoView` on the target thumbnail rather than
 * computing a pixel offset with `scrollBy`: `scrollLeft` sign conventions
 * differ across browsers on RTL pages (this site is Arabic/RTL), so raw
 * left/right math would silently reverse the arrows in some browsers.
 */
export class ProductPageThumbnailsSlider extends Interaction {
    static selector = ".o_product_page_thumbnails";
    dynamicContent = {
        ".o_product_page_thumbnails_prev": { "t-on-click": this.scrollPrev },
        ".o_product_page_thumbnails_next": { "t-on-click": this.scrollNext },
    };

    setup() {
        this.boxes = Array.from(
            this.el.querySelectorAll(".o_product_page_thumbnail_box")
        );
        this.index = 0;
    }

    scrollPrev() {
        this._scrollTo(this.index - STEP);
    }

    scrollNext() {
        this._scrollTo(this.index + STEP);
    }

    _scrollTo(index) {
        if (!this.boxes.length) {
            return;
        }
        this.index = Math.max(0, Math.min(index, this.boxes.length - 1));
        this.boxes[this.index].scrollIntoView({
            behavior: "smooth",
            inline: "start",
            block: "nearest",
        });
    }
}

registry
    .category("public.interactions")
    .add("product_page_thumbnails.slider", ProductPageThumbnailsSlider);
