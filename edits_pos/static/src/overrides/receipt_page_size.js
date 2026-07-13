import { patch } from "@web/core/utils/patch";
import { PrinterService } from "@point_of_sale/app/services/printer_service";
import { waitImages } from "@point_of_sale/utils";

const STYLE_ID = "edits_pos_receipt_page_size";
const PX_PER_MM = 96 / 25.4;
const PRINT_WIDTH_PX = 266;
const PRINT_FONT_PX = 14;
const HEIGHT_SLACK_MM = 2;

function measureReceipt() {
    const receipt = document.querySelector(".render-container .pos-receipt");
    if (!receipt) {
        return null;
    }

    const saved = receipt.getAttribute("style");
    receipt.style.width = `${PRINT_WIDTH_PX}px`;
    receipt.style.fontSize = `${PRINT_FONT_PX}px`;
    const { width, height } = receipt.getBoundingClientRect();
    if (saved === null) {
        receipt.removeAttribute("style");
    } else {
        receipt.setAttribute("style", saved);
    }
    return height ? { width: width / PX_PER_MM, height: height / PX_PER_MM } : null;
}

export function sizePageToReceipt() {
    const receipt = measureReceipt();
    let style = document.getElementById(STYLE_ID);
    if (!receipt) {
        style?.remove();
        return;
    }
    if (!style) {
        style = document.createElement("style");
        style.id = STYLE_ID;
        document.head.appendChild(style);
    }
    const width = Math.ceil(receipt.width);
    const height = Math.ceil(receipt.height + HEIGHT_SLACK_MM);
    style.textContent = `@page { size: ${width}mm ${height}mm; margin: 0; }`;
}

window.addEventListener("beforeprint", sizePageToReceipt);

patch(PrinterService.prototype, {
    printWeb(el) {
        this.renderer.whenMounted({
            el,
            callback: async (el) => {
                await waitImages(el);
                sizePageToReceipt();
                window.print(el);
            },
        });
        return true;
    },
});
