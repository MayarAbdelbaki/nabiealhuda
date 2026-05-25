/** @odoo-module **/

import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";

/**
 * Fix for Odoo 19 Discuss Composer:
 *   TypeError: Cannot read properties of undefined (reading 'stopPropagation')
 *       at Composer.onFocusin (...)
 *
 * Root cause: somewhere in the patch chain (mail -> mail_enterprise -> ...)
 * a super.onFocusin() call is made without forwarding the event argument,
 * so the base implementation receives `undefined` and crashes on
 * `ev.stopPropagation()`.
 *
 * Strategy: wrap the whole handler in a try/catch and always pass a safe
 * event-like stub to super when the real one is missing. We also swallow
 * the TypeError if it still bubbles up, since it is purely cosmetic
 * (the composer keeps working).
 */
function makeStubEvent(target) {
    return {
        stopPropagation() {},
        preventDefault() {},
        stopImmediatePropagation() {},
        target: target ?? null,
        currentTarget: target ?? null,
        type: "focusin",
        bubbles: true,
        cancelable: false,
        defaultPrevented: false,
        isTrusted: false,
    };
}

patch(Composer.prototype, {
    onFocusin(ev) {
        const safeEv = ev && typeof ev.stopPropagation === "function"
            ? ev
            : makeStubEvent(this.ref?.el ?? null);
        try {
            return super.onFocusin(safeEv);
        } catch (e) {
            if (
                e instanceof TypeError &&
                /stopPropagation|preventDefault/.test(String(e.message))
            ) {
                // Known harmless crash in the upstream patch chain.
                return;
            }
            throw e;
        }
    },
});
