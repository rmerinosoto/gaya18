/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class SalesFieldDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const actionContext =
            (this.props && this.props.action && this.props.action.context) || {};
        const managerOnly = Boolean(actionContext.manager_only);
        const now = new Date();
        const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
        this.state = useState({
            loading: true,
            managerOnly,
            filters: {
                month: defaultMonth,
                userId: "",
            },
            data: {
                kpis: {},
                lists: {},
                actions: {},
                currency: { symbol: "$", position: "before" },
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const kwargs = {};
            if (this.state.filters.month) {
                kwargs.date_ref = `${this.state.filters.month}-01`;
            }
            if (this.state.filters.userId) {
                kwargs.target_user_id = parseInt(this.state.filters.userId, 10);
            }
            this.state.data = await this.orm.call(
                "sales.field.dashboard",
                "get_dashboard_data",
                [],
                kwargs
            );
            if (!this.state.filters.userId && this.state.data.selected_user) {
                this.state.filters.userId = String(this.state.data.selected_user.id);
            }
        } finally {
            this.state.loading = false;
        }
    }

    labelType(key) {
        const labels = (this.state.data && this.state.data.labels && this.state.data.labels.interaction_type) || {};
        return labels[key] || key;
    }

    labelResult(key) {
        const labels = (this.state.data && this.state.data.labels && this.state.data.labels.result) || {};
        return labels[key] || key;
    }

    /**
     * D-03: opciones del select de mes. Mes actual + 5 meses hacia atras.
     * Label en formato "Mayo 2026" para lectura natural; value en YYYY-MM
     * para compatibilidad con la lectura del backend.
     */
    monthOptions() {
        const months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ];
        const opts = [];
        const now = new Date();
        for (let i = 0; i < 6; i++) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
            let label = `${months[d.getMonth()]} ${d.getFullYear()}`;
            if (i === 0) label = `Este mes (${label})`;
            else if (i === 1) label = `Mes anterior (${label})`;
            opts.push({ value, label });
        }
        // Si el filtro actual es un mes mas antiguo que el rango, agregarlo para no perderlo.
        if (this.state.filters.month && !opts.some((o) => o.value === this.state.filters.month)) {
            const [y, m] = this.state.filters.month.split("-").map((x) => parseInt(x, 10));
            opts.push({ value: this.state.filters.month, label: `${months[m - 1]} ${y}` });
        }
        return opts;
    }

    formatMoney(value) {
        const amount = Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        const currency = this.state.data.currency || { symbol: "$", position: "before" };
        return currency.position === "after" ? `${amount} ${currency.symbol}` : `${currency.symbol} ${amount}`;
    }

    openAction(actionKey) {
        const actions = (this.state.data && this.state.data.actions) || {};
        const act = actions[actionKey];
        if (act) {
            if (act.type === "ir.actions.act_window" && !act.views && act.view_mode) {
                act.views = act.view_mode
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean)
                    .map((v) => [false, v]);
            }
            this.action.doAction(act);
        }
    }

    onKpiClick(ev) {
        const actionKey = ev.currentTarget.dataset.actionKey;
        this.openAction(actionKey);
    }

    onActionClick(ev) {
        const actionKey = ev.currentTarget.dataset.actionKey;
        this.openAction(actionKey);
    }

    async onMonthChange(ev) {
        this.state.filters.month = ev.target.value || this.state.filters.month;
        await this.loadData();
    }

    async onUserChange(ev) {
        this.state.filters.userId = ev.target.value || "";
        await this.loadData();
    }

    onInteractionClick(ev) {
        const recordId = parseInt(ev.currentTarget.dataset.recordId, 10);
        if (recordId) {
            this.openInteraction(recordId);
        }
    }

    /**
     * Click en cliente del bloque "Sin contacto 30 dias" abre el form de una
     * NUEVA interaccion con ese cliente precargado. La logica: si esta ahi es
     * porque hay que contactarlo, no porque haya que mirarle la ficha.
     */
    onInactivePartnerClick(ev) {
        const partnerId = parseInt(ev.currentTarget.dataset.recordId, 10);
        if (!partnerId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sales.interaction",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_partner_id: partnerId,
                default_user_id: this.state.data.selected_user && this.state.data.selected_user.id,
            },
        });
    }

    /**
     * D-01: true cuando el mes filtrado no tiene actividad ni pendientes y
     * conviene mostrar el empty state contextual ("registra tu primer
     * contacto") en vez de 9 ceros mudos. Si hay algo pendiente (hoy/semana/
     * atrasado) NO mostramos el CTA porque el vendedor ya tiene trabajo
     * cargado de meses anteriores.
     */
    isMonthEmpty() {
        const k = (this.state.data && this.state.data.kpis) || {};
        const l = (this.state.data && this.state.data.lists) || {};
        const counters = [
            k.total_interactions,
            k.quotations_month,
            k.prospect_contacted,
            k.customer_contacted,
        ];
        const noActivity = counters.every((v) => !v);
        const noPending = !(l.due_today || []).length
            && !(l.due_this_week || []).length
            && !(l.overdue || []).length;
        return noActivity && noPending;
    }

    onCreateInteraction() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sales.interaction",
            views: [[false, "form"]],
            target: "current",
            context: { default_user_id: this.state.data.selected_user && this.state.data.selected_user.id },
        });
    }

    openInteraction(recordId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sales.interaction",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

SalesFieldDashboard.template = "sales_field_sfa.Dashboard";
registry.category("actions").add("sales_field_sfa.dashboard", SalesFieldDashboard);
