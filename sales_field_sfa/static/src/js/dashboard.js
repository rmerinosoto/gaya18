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

    onPartnerClick(ev) {
        const recordId = parseInt(ev.currentTarget.dataset.recordId, 10);
        if (recordId) {
            this.openPartner(recordId);
        }
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

    openPartner(recordId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

SalesFieldDashboard.template = "sales_field_sfa.Dashboard";
registry.category("actions").add("sales_field_sfa.dashboard", SalesFieldDashboard);
