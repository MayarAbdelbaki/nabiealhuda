import { patch } from "@web/core/utils/patch";
import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { waitImages } from "@point_of_sale/utils";
import { sizePageToReceipt } from "@edits_pos/overrides/receipt_page_size";

const ILLEGAL_IN_FILENAME = /[\\/:*?"<>|]+/g;

function invoiceNumberOf(el) {
    const raw = el?.querySelector(".edits-invoice-no")?.textContent?.trim();
    return raw ? raw.replace(ILLEGAL_IN_FILENAME, "-") : null;
}

function printTitledAs(name) {
    const original = document.title;
    if (!name) {
        window.print();
        return;
    }
    const restore = () => {
        document.title = original;
        window.removeEventListener("afterprint", restore);
    };
    window.addEventListener("afterprint", restore);
    document.title = name;
    window.print();
    setTimeout(restore, 5000);
}

// The single override of printWeb. receipt_page_size.js deliberately does not patch it
// too: a second override of the same method would silently replace this one.
patch(PrinterService.prototype, {
    // Same as the original, but once the receipt is mounted and its images have loaded,
    // size the page to it and name the print job, both before the dialog reads them.
    printWeb(el) {
        this.renderer.whenMounted({
            el,
            callback: async (el) => {
                await waitImages(el);
                sizePageToReceipt();
                printTitledAs(invoiceNumberOf(el));
            },
        });
        return true;
    },
});
window.addEventListener("beforeprint", () => {
    const receipt = document.querySelector(".render-container .pos-receipt");
    const number = invoiceNumberOf(receipt);
    if (number && document.title !== number) {
        document.title = number;
    }
});
