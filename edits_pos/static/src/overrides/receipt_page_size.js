/**
 * Prints the receipt as one continuous page instead of breaking it across sheets.
 *
 * Chrome ignores `@page { size: <width> auto }`, so the page height cannot be left to the
 * browser: it has to be measured off the receipt and written out explicitly before the
 * print dialog opens.
 *
 * This needs a destination that accepts an arbitrary paper size. Chrome's built-in
 * "Save as PDF" does; a real printer driver only offers the paper sizes it declares and
 * will fall back to the closest one it has.
 *
 * No patch of PrinterService here on purpose: receipt_filename.js already overrides
 * printWeb, and a second override of the same method would silently replace the first.
 * It calls sizePageToReceipt() for us.
 */

const STYLE_ID = "edits_pos_receipt_page_size";
const PX_PER_MM = 96 / 25.4;

// Keep in step with the printed receipt width in pos_receipt.css.
const RECEIPT_WIDTH_MM = 80;
const RECEIPT_FONT = "10pt";
/**
 * Spare millimetres added to the measured height.
 *
 * Erring high costs a thin blank strip at the foot of the page; erring low costs a whole
 * extra sheet, because the company/QR block is break-inside:avoid and jumps as one piece
 * the moment it is a hair too tall for the space left. A few millimetres is enough to
 * absorb rounding.
 */
const HEIGHT_SLACK_MM = 4;

function measureReceiptHeightMm() {
    const receipt = document.querySelector(".render-container .pos-receipt");
    if (!receipt) {
        return null;
    }
    // The print geometry only takes effect under @media print, so impose it here to
    // measure the height the receipt will really have on paper rather than on screen.
    const saved = receipt.getAttribute("style");
    receipt.style.width = `${RECEIPT_WIDTH_MM}mm`;
    receipt.style.fontSize = RECEIPT_FONT;
    const { height } = receipt.getBoundingClientRect();
    if (saved === null) {
        receipt.removeAttribute("style");
    } else {
        receipt.setAttribute("style", saved);
    }
    return height ? height / PX_PER_MM : null;
}

export function sizePageToReceipt() {
    const height = measureReceiptHeightMm();
    let style = document.getElementById(STYLE_ID);
    if (!height) {
        // Nothing is staged for printing: leave the browser's default paper alone.
        style?.remove();
        return;
    }
    if (!style) {
        style = document.createElement("style");
        style.id = STYLE_ID;
        document.head.appendChild(style);
    }
    const pageHeight = Math.ceil(height + HEIGHT_SLACK_MM);
    // padding:0 is not optional -- point_of_sale sets `@page { padding: 15px }` and Chrome
    // honours it, shrinking the printable area by 30px on each axis. See pos_receipt.css.
    style.textContent =
        `@page { size: ${RECEIPT_WIDTH_MM}mm ${pageHeight}mm; margin: 0; padding: 0; }`;
}

// Covers a manual Ctrl+P while a receipt is staged for printing.
window.addEventListener("beforeprint", sizePageToReceipt);
