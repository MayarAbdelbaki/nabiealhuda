/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

// How many thumbnails a single arrow click slides past.
const STEP = 3;

/**
 * Small thumbnail strip on the product page.
 *
 * - Prev/next arrows: the track only shows a few thumbnails at a time (see
 *   the CSS `max-width` on `.o_product_page_thumbnails_track`) and arrows
 *   slide through the rest, instead of showing every thumbnail at once.
 *   Scrolls via `scrollIntoView` on the target thumbnail rather than a
 *   pixel offset with `scrollBy`: `scrollLeft` sign conventions differ
 *   across browsers on RTL pages (this site is Arabic/RTL), so raw
 *   left/right math would silently reverse the arrows in some browsers.
 *
 * - Clicking a thumbnail switches the main image: that part needs no JS
 *   here — the thumbnails carry the same `data-bs-target`/`data-bs-slide-to`
 *   attributes Odoo's own carousel indicators use, and Bootstrap's carousel
 *   picks up clicks on any element with those attributes via a
 *   document-level delegated listener. This class only keeps the "active"
 *   highlight and the strip's scroll position in sync afterwards, including
 *   when the image changes some other way (the main carousel's own arrows,
 *   swipe, keyboard).
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

        this.carousel = document.getElementById("o-carousel-product");
        if (this.carousel) {
            this.onSlid = (ev) => this._syncActive(ev.to);
            this.carousel.addEventListener("slid.bs.carousel", this.onSlid);
            this.registerCleanup(() =>
                this.carousel.removeEventListener("slid.bs.carousel", this.onSlid)
            );
        }
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

    _syncActive(activeIndex) {
        this.index = activeIndex;
        this.boxes.forEach((box, i) => box.classList.toggle("active", i === activeIndex));
        this.boxes[activeIndex]?.scrollIntoView({
            behavior: "smooth",
            inline: "start",
            block: "nearest",
        });
    }
}

registry
    .category("public.interactions")
    .add("product_page_thumbnails.slider", ProductPageThumbnailsSlider);
