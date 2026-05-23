from odoo.tests.common import TransactionCase


class SFACommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.User = cls.env["res.users"]
        cls.Partner = cls.env["res.partner"]
        cls.Interaction = cls.env["sales.interaction"]

        cls.group_user = cls.env.ref("sales_field_sfa.group_sales_field_user")
        cls.group_manager = cls.env.ref("sales_field_sfa.group_sales_field_manager")
        cls.group_sale_salesman = cls.env.ref("sales_team.group_sale_salesman")

        cls.seller_a = cls.User.create({
            "name": "Vendedor A SFA Test",
            "login": "sfa_test_seller_a",
            "email": "sfa_test_seller_a@example.test",
            "groups_id": [(6, 0, [cls.group_user.id, cls.group_sale_salesman.id])],
        })
        cls.seller_b = cls.User.create({
            "name": "Vendedor B SFA Test",
            "login": "sfa_test_seller_b",
            "email": "sfa_test_seller_b@example.test",
            "groups_id": [(6, 0, [cls.group_user.id, cls.group_sale_salesman.id])],
        })
        cls.manager = cls.User.create({
            "name": "Gerente SFA Test",
            "login": "sfa_test_manager",
            "email": "sfa_test_manager@example.test",
            "groups_id": [(6, 0, [cls.group_manager.id, cls.group_sale_salesman.id])],
        })

        cls.partner_orphan = cls.Partner.create({"name": "Cliente Huerfano SFA"})
        cls.partner_owned_by_b = cls.Partner.create({
            "name": "Cliente de B SFA",
            "user_id": cls.seller_b.id,
        })
