from odoo import http
from odoo.http import request


class SalesFieldSFAController(http.Controller):
    @http.route("/sales_field_sfa/dashboard_data", type="json", auth="user")
    def dashboard_data(self):
        return request.env["sales.field.dashboard"].get_dashboard_data()
