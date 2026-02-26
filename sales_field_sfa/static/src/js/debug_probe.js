/** @odoo-module **/

console.log("[sales_field_sfa][probe] web.assets_backend cargado");

window.addEventListener("error", (ev) => {
    console.error("[sales_field_sfa][probe] window.error", {
        message: ev.message,
        filename: ev.filename,
        lineno: ev.lineno,
        colno: ev.colno,
        error: ev.error,
    });
});

window.addEventListener("unhandledrejection", (ev) => {
    console.error("[sales_field_sfa][probe] unhandledrejection", ev.reason);
});
