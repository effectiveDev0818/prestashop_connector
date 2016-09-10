# -*-# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp.exceptions import ValidationError
from openerp import api, fields, models, _
from openerp.addons.decimal_precision import decimal_precision as dp


class ProductProduct(models.Model):
    _inherit = 'product.product'

    prestashop_combinations_bind_ids = fields.One2many(
        comodel_name='prestashop.product.combination',
        inverse_name='odoo_id',
        string='PrestaShop Bindings (combinations)',
    )
    default_on = fields.Boolean(string='Default On')
    impact_price = fields.Float(
        string="Price Impact", digits=dp.get_precision('Product Price'))

    @api.multi
    @api.depends('impact_price', 'product_tmpl_id.list_price')
    def _compute_lst_price(self):
        for product in self:
            price = product.list_price + product.impact_price
            if 'uom' in self.env.context:
                uom = product.uos_id or product.uom_id
                price = uom._compute_price(
                    product.uom_id.id, price, self.env.context['uom'])
            product.lst_price = price

    lst_price = fields.Float(
        compute='_compute_lst_price')

    @api.multi
    def _check_default_on(self):
        if self.env.context.get('skip_check_default_variant', False):
            return True
        for product in self:
            if product.product_tmpl_id.product_variant_count > 1:
                product_ids = self.search([
                    ('default_on', '=', True),
                    ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ])
                if len(product_ids) == 0 or len(product_ids) > 1:
                    return False
        return True

    @api.model
    def create(self, vals):
        if 'product_tmpl_id' in vals:
            template = self.env['product.template'].browse(
                vals['product_tmpl_id'])
            if template.product_variant_ids:
                vals['default_on'] = not template.product_variant_ids.filtered(
                    lambda x: x.default_on)
            return super(ProductProduct, self).create(vals)
        else:
            product = super(ProductProduct, self).create(vals)
            value = not product.product_variant_ids.filtered(
                lambda x: x.default_on)
            product.with_context(connector_no_export=True).default_on = value
            return product

    @api.multi
    def write(self, vals):
        res = super(ProductProduct, self).write(vals)
        if not self.env.context.get('skip_check_default_variant', False):
            for product in self:
                template = product.product_tmpl_id
                if 'default_on' in vals and template.product_variant_count > 1:
                    old_default_var = template.product_variant_ids.filtered(
                        lambda x: x.default_on and x.id != product.id)
                    if old_default_var:
                        old_default_var.with_context(
                            skip_check_default_variant=True,
                            connector_no_export=True,
                        ).default_on = False
        if self._check_default_on():
            return res
        else:
            raise ValidationError(_('Error! Only one variant can be default '
                                    'and one is required as default'))

    @api.multi
    def open_product_template(self):
        """
        Utility method used to add an "Open Product Template"
        button in product.product views
        """
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'product.template',
                'view_mode': 'form',
                'res_id': self.product_tmpl_id.id,
                'target': 'new',
                'flags': {'form': {'action_buttons': True}}}


class PrestashopProductCombination(models.Model):
    _name = 'prestashop.product.combination'
    _inherit = 'prestashop.binding.odoo'
    _inherits = {'product.product': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
        ondelete='cascade',
        oldname='openerp_id',
    )
    main_template_id = fields.Many2one(
        comodel_name='prestashop.product.template',
        string='Main Template',
        required=True,
        ondelete='cascade',
    )
    quantity = fields.Float(
        string='Computed Quantity',
        help='Last computed quantity to send on PrestaShop.'
    )
    reference = fields.Char(string='Original reference')

    @api.multi
    def recompute_prestashop_qty(self):
        for product_binding in self:
            if product_binding.quantity != product_binding.qty_available:
                product_binding.quantity = product_binding.qty_available
        return True

    @api.model
    def _prestashop_qty(self, product):
        return product.qty_available


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    prestashop_bind_ids = fields.One2many(
        comodel_name='prestashop.product.combination.option',
        inverse_name='odoo_id',
        string='PrestaShop Bindings (combinations)',
    )


class PrestashopProductCombinationOption(models.Model):
    _name = 'prestashop.product.combination.option'
    _inherit = 'prestashop.binding.odoo'
    _inherits = {'product.attribute': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='product.attribute',
        string='Attribute',
        required=True,
        ondelete='cascade',
        oldname='openerp_id',
    )
    prestashop_position = fields.Integer('PrestaShop Position')
    group_type = fields.Selection([
        ('color', 'Color'),
        ('radio', 'Radio'),
        ('select', 'Select')], string='Type', default='select')
    public_name = fields.Char(string='Public Name', translate=True)


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    prestashop_bind_ids = fields.One2many(
        comodel_name='prestashop.product.combination.option.value',
        inverse_name='odoo_id',
        string='PrestaShop Bindings',
    )


class PrestashopProductCombinationOptionValue(models.Model):
    _name = 'prestashop.product.combination.option.value'
    _inherit = 'prestashop.binding'
    _inherits = {'product.attribute.value': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='product.attribute.value',
        string='Attribute',
        required=True,
        ondelete='cascade',
        oldname='openerp_id',
    )
    prestashop_position = fields.Integer(
        string='PrestaShop Position',
        default=1,
    )
    id_attribute_group = fields.Many2one(
        comodel_name='prestashop.product.combination.option')
