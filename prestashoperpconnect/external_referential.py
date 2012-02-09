# -*- encoding: utf-8 -*-
###############################################################################
#                                                                             #
#   Prestashoperpconnect for OpenERP                                          #
#   Copyright (C) 2012 Akretion                                               #
#   Author :                                                                  #
#           Sébastien BEAU <sebastien.beau@akretion.com>                      #
#           Alexis de Lattre <alexis.delattre@akretion.com>                   #
#                                                                             #
#   This program is free software: you can redistribute it and/or modify      #
#   it under the terms of the GNU Affero General Public License as            #
#   published by the Free Software Foundation, either version 3 of the        #
#   License, or (at your option) any later version.                           #
#                                                                             #
#   This program is distributed in the hope that it will be useful,           #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of            #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Affero General Public License for more details.                       #
#                                                                             #
#   You should have received a copy of the GNU Affero General Public License  #
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

from osv import osv, fields
from tools.translate import _
from base_external_referentials.decorator import only_for_referential
from prestapyt import PrestaShopWebServiceError, PrestaShopWebService, PrestaShopWebServiceDict
from prestashop_osv import prestashop_osv

class external_referential(prestashop_osv):
    _inherit = "external.referential"
    
    @only_for_referential('prestashop')
    def external_connection(self, cr, uid, id, debug=False, context=None):
        if isinstance(id, list):
            id=id[0]
        referential = self.browse(cr, uid, id, context=context)
        prestashop = PrestaShopWebServiceDict('%s/api'%referential.location, referential.apipass)
        try:
            prestashop.head('')
        except Exception, e:
            raise osv.except_osv(_("Connection Error"), _("Could not connect to server\nCheck url & password.\n %s"%e))
        return prestashop


    def _map_ps_lang(self, cr, uid, external_session, context=None):
        """Synchronise OERP res.lang and PS languages"""
        external_session.logger.info(_("Starting synchro of languages between OERP and PS"))
        referential_id = external_session.referential_id.id
        nr_ps_already_mapped = 0
        nr_ps_mapped = 0
        nr_ps_not_mapped = 0
        # Get all OERP res.lang
        lang_obj = self.pool.get('res.lang')
        oe_lang_ids = lang_obj.search(cr, uid, [], context=context)
        oe_langs = lang_obj.read(cr, uid, oe_lang_ids, ['code', 'name'], context=context)
        print "oe_langs=", oe_langs
        # Get the language IDS from PS
        res_ps_lang = lang_obj._get_external_resource_ids(cr, uid, external_session, context=context)
        print "res_ps_lang=", res_ps_lang
        # Hack to put the languages IDs from PS in a clean list
        # (waiting for a fix in prestapyth)
        ps_lang_list = []
        for ps_lang in res_ps_lang:
            ps_lang_list.append(ps_lang['attrs']['id'])
        print "ps_lang_list =", ps_lang_list
        # Loop on all PS languages
        for ps_lang_id in ps_lang_list:
            # Check if the PS language is already mapped to an OE language
            oe_lang_id = lang_obj.extid_to_existing_oeid(cr, uid, external_id=ps_lang_id,
                referential_id=referential_id, context=context)
            print "oe_lang_id=", oe_lang_id
            if oe_lang_id:
                # Do nothing for the PS IDs are already mapped
                external_session.logger.debug(_("PS lang ID %s is already mapped to OERP lang ID %s") %(ps_lang_id, oe_lang_id))
                nr_ps_already_mapped += 1
            else:
                # PS IDs not mapped => I try to match between the PS lang and the OE lang
                # I read field in PS
                ps_lang_dict = lang_obj._get_external_resources(cr, uid, external_session,
                    ps_lang_id, context=context)
                print "ps_lang_dict=", ps_lang_dict
                mapping_found = False
                # Loop on OE langs
                for oe_lang in oe_langs:
                    # Search for a match
                    if len(oe_lang['code']) >= 2 and len(ps_lang_dict[0]['language_code']) >=2 and oe_lang['code'][0:2].lower() == ps_lang_dict[0]['language_code'][0:2].lower():
                        # it matches, so I write the external ID
                        lang_obj.create_external_id_vals(cr, uid,
                            existing_rec_id=oe_lang['id'], external_id=ps_lang_id,
                            referential_id=referential_id, context=context)
                        external_session.logger.info(
                            _("Mapping PS lang '%s' (%s) to OERP lang '%s' (%s)")
                            %(ps_lang_dict[0]['name'], ps_lang_dict[0]['language_code'],
                            oe_lang['name'], oe_lang['code']))
                        nr_ps_mapped += 1
                        mapping_found = True
                        break
                if not mapping_found:
                    # if it doesn't match, I just print a warning
                    external_session.logger.warning(
                        _("PS lang '%s' (%s) was not mapped to any OERP lang")
                        %(ps_lang_dict[0]['name'], ps_lang_dict[0]['language_code']))
                    nr_ps_not_mapped += 1
        external_session.logger.info(_("Synchro of languages between OERP and PS successfull"))
        external_session.logger.info(_("Number of PS languages already mapped = %s")
            % nr_ps_already_mapped)
        external_session.logger.info(_("Number of PS languages mapped = %s")
            % nr_ps_mapped)
        external_session.logger.info(_("Number of PS languages not mapped = %s")
            % nr_ps_not_mapped)

        return True


    def _map_ps_country(self, cr, uid, external_session, context=None):
        """Synchronise OERP res.country and PS countries"""
        external_session.logger.info(_("Starting synchro of countries between OERP and PS"))
        referential_id = external_session.referential_id.id
        nr_ps_already_mapped = 0
        nr_ps_mapped = 0
        nr_ps_not_mapped = 0
        # Get all OERP res.country
        country_obj = self.pool.get('res.country')
        oe_country_ids = country_obj.search(cr, uid, [], context=context)
        oe_countries = country_obj.read(cr, uid, oe_country_ids, ['code', 'name'], context=context)
        print "oe_coutrnies=", oe_countries
        # Get the country IDS from PS
        ps_country_list = country_obj._get_external_resource_ids(cr, uid, external_session, context=context)
        print "ps_country_list=", ps_country_list
        # Loop on all PS countries
        for ps_country_id in ps_country_list:
            # Check if the PS country is already mapped to an OE country
            oe_country_id = country_obj.extid_to_existing_oeid(cr, uid, external_id=ps_country_id, referential_id=referential_id, context=context)
            print "oe_c_id=", oe_country_id
            if oe_country_id:
                # Do nothing for the PS IDs are already mapped
                external_session.logger.debug(_("PS country ID %s is already mapped to OERP country ID %s") %(ps_country_id, oe_country_id))
                nr_ps_already_mapped += 1
            else:
                # PS IDs not mapped => I try to match between the PS country and the OE country
                # I read field in PS
                ps_country_dict = country_obj._get_external_resources(cr, uid, external_session, ps_country_id, context=context)
                print "ps_country_dict=", ps_country_dict
                mapping_found = False
                # Loop on OE countries
                for oe_country in oe_countries:
                    # Search for a match
                    if len(oe_country['code']) >= 2 and len(ps_country_dict[0]['iso_code']) >=2 and oe_country['code'][0:2].lower() == ps_country_dict[0]['iso_code'][0:2].lower():
                        # it matches, so I write the external ID
                        country_obj.create_external_id_vals(cr, uid, existing_rec_id=oe_country['id'], external_id=ps_country_id, referential_id=referential_id, context=context)
                        external_session.logger.info(_("Mapping PS country '%s' (%s) to OERP country '%s' (%s)") %(ps_country_dict[0]['name'], ps_country_dict[0]['iso_code'], oe_country['name'], oe_country['code']))
                        nr_ps_mapped += 1
                        mapping_found = True
                        break
                if not mapping_found:
                    # if it doesn't match, I just print a warning
                    external_session.logger.warning(_("PS country '%s' (%s) was not mapped to any OERP country") %(ps_country_dict[0]['name'], ps_country_dict[0]['iso_code']))
                    nr_ps_not_mapped += 1
        external_session.logger.info(_("Synchro of countries between OERP and PS successfull"))
        external_session.logger.info(_("Number of PS countries already mapped = %s")
            % nr_ps_already_mapped)
        external_session.logger.info(_("Number of PS countries mapped = %s")
            % nr_ps_mapped)
        external_session.logger.info(_("Number of PS countries not mapped = %s")
            % nr_ps_not_mapped)
        return True


    @only_for_referential('prestashop')
    def _import_resources(self, cr, uid, external_session, defaults=None, context=None, method="search_then_read"):
        referential_id = external_session.referential_id.id
        self.import_resources(cr, uid, [referential_id], 'external.shop.group', context=context)
        self.import_resources(cr, uid, [referential_id], 'sale.shop', context=context)
        self._map_ps_country(cr, uid, external_session, context=context)
        self._map_ps_lang(cr, uid, external_session, context=context)
        return {}

class external_shop_group(prestashop_osv):
    _inherit='external.shop.group'

class sale_shop(prestashop_osv):
    _inherit='sale.shop'

class res_lang(prestashop_osv):
    _inherit='res.lang'

class res_country(prestashop_osv):
    _inherit='res.country'

class sale_order(prestashop_osv):
    _inherit='sale.order'
