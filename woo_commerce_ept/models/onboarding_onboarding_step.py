# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

woo_instance_ref = 'woo.instance.ept'
ir_actions_ref = 'ir.actions.actions'

class OnbordingStep(models.Model):
    """
    This model is inherited for adding onboarding process.
    @author: Dhaval Bhut on Date 01-Nov-2023
    """
    _inherit = 'onboarding.onboarding.step'

    # action_woo_open_cron_configuration_wizard

    # self.action_validate_step("shopify_ept.onboarding_onboarding_step_shopify_cron_configuration_configure")

    def woo_res_config_view_action(self, view_id):
        """
        Usage: return the action for open the configurations wizard
        """
        woo_instance_obj = self.env[woo_instance_ref]
        action = self.env[ir_actions_ref]._for_xml_id(
            "woo_commerce_ept.action_woo_config")
        action_data = {'view_id': view_id.id, 'views': [(view_id.id, 'form')], 'target': 'new',
                       'name': 'Configurations'}
        instance = woo_instance_obj.search_woo_instance()
        if instance:
            action['context'] = {'default_woo_instance_id': instance.id}
        else:
            action['context'] = {}
        action.update(action_data)
        return action

    @api.model
    def action_open_woo_instance_wizard(self):
        """
        Called by onboarding panel above the Instance.
        """
        ir_action_obj = self.env[ir_actions_ref]
        instance_obj = self.env[woo_instance_ref]
        action = ir_action_obj._for_xml_id(
            "woo_commerce_ept.woo_on_board_instance_configuration_action")
        action['context'] = {'is_calling_from_onboarding_panel': True}
        instance = instance_obj.search_woo_instance()
        if instance:
            action.get('context').update({
                'default_name': instance.name,
                'default_woo_host': instance.woo_host,
                'default_store_timezone': instance.store_timezone,
                'default_woo_company_id': instance.company_id.id,
                'default_woo_consumer_key': instance.woo_consumer_key,
                'default_woo_consumer_secret': instance.woo_consumer_secret,
                'default_woo_verify_ssl': instance.woo_verify_ssl,
                'default_is_export_update_images': instance.is_export_update_images,
                'default_woo_admin_username': instance.woo_admin_username,
                'default_woo_admin_password': instance.woo_admin_password,
                'is_already_instance_created': True,
            })
            company = instance.company_id
        return action

    @api.model
    def action_woo_open_basic_configuration_wizard(self):
        """
        Called by onboarding panel above the Instance.
        Usage: return the action for open the basic configurations wizard
        """
        try:
            view_id = self.env.ref('woo_commerce_ept.woo_basic_configurations_onboarding_wizard_view')
        except Exception:
            return True
        return self.woo_res_config_view_action(view_id)

    @api.model
    def action_woo_open_financial_status_wizard(self):
        """
        Usage: return the action for open the basic configurations wizard
        Called by onboarding panel above the Instance.
        """
        try:
            view_id = self.env.ref('woo_commerce_ept.woo_financial_status_onboarding_wizard_view')
        except Exception:
            return True
        return self.woo_res_config_view_action(view_id)

    @api.model
    def action_woo_open_cron_configuration_wizard(self):
        """
       Usage: Return the action for open the cron configuration wizard
       @author: Dipak Gogiya
       Migrated by Maulik Barad on Date 07-Oct-2021.
        """
        """ Called by onboarding panel above the Instance."""
        instance_obj = self.env[woo_instance_ref]
        ir_action_obj = self.env[ir_actions_ref]
        action = ir_action_obj._for_xml_id(
            "woo_commerce_ept.action_wizard_woo_cron_configuration_ept")
        instance = instance_obj.search_woo_instance()
        action['context'] = {'is_calling_from_onboarding_panel': True}
        if instance:
            action.get('context').update({'default_woo_instance_id': instance.id,
                                          'is_instance_exists': True})
        return action
