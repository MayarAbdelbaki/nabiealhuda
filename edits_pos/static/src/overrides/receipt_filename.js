import { patch } from "@web/core/utils/patch";
import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { waitImages } from "@point_of_sale/utils";

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

patch(PrinterService.prototype, {
    printWeb(el) {
        this.renderer.whenMounted({
            el,
            callback: async (el) => {
                await waitImages(el);
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
