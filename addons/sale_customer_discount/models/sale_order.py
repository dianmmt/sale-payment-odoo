from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    order_count = fields.Integer(string='Số lượt mua hàng', compute='_compute_order_count', store=False)
    loyalty_discount = fields.Boolean(string='Áp dụng giảm giá thân thiết', default=False)
    loyalty_discount_applied = fields.Boolean(string='Đã áp dụng giảm giá thân thiết', default=False)
    loyalty_discount_percentage = fields.Float(string='Phần trăm giảm giá', compute='_compute_discount_percentage', store=True)
    loyalty_discount_amount = fields.Monetary(string='Số tiền giảm giá', compute='_compute_discount_amount', store=True)

    @api.depends('partner_id')
    def _compute_order_count(self):
        """Tính toán số lượng đơn hàng đã hoàn thành của khách hàng"""
        for order in self:
            if order.partner_id:
                # Đếm số đơn hàng đã hoàn thành của khách hàng (không tính đơn hàng hiện tại)
                domain = [
                    ('partner_id', '=', order.partner_id.id),
                    ('state', '=', 'sale'),  # Chỉ đếm đơn hàng đã xác nhận
                ]
                
                # Chỉ thêm điều kiện loại trừ ID nếu ID là hợp lệ (không phải NewId)
                if hasattr(order, 'id') and not isinstance(order.id, models.NewId) and order.id:
                    domain.append(('id', '!=', order.id))
                
                order.order_count = self.env['sale.order'].search_count(domain)
            else:
                order.order_count = 0

    # Giữ nguyên các phương thức khác như đã định nghĩa
    @api.depends('order_count')
    def _compute_discount_percentage(self):
        """Xác định phần trăm giảm giá dựa trên số lượng đơn hàng"""
        for order in self:
            # Mức giảm giá tùy thuộc vào số lượt mua hàng
            if order.order_count >= 10:
                order.loyalty_discount_percentage = 15.0
            elif order.order_count >= 5:
                order.loyalty_discount_percentage = 10.0
            elif order.order_count >= 3:
                order.loyalty_discount_percentage = 7.0
            elif order.order_count >= 1:
                order.loyalty_discount_percentage = 5.0
            else:
                order.loyalty_discount_percentage = 0.0

    @api.depends('amount_untaxed', 'loyalty_discount_percentage', 'loyalty_discount')
    def _compute_discount_amount(self):
        """Tính toán số tiền giảm giá dựa trên phần trăm và tổng giá trị đơn hàng"""
        for order in self:
            if order.loyalty_discount and order.loyalty_discount_percentage > 0:
                order.loyalty_discount_amount = order.amount_untaxed * (order.loyalty_discount_percentage / 100.0)
            else:
                order.loyalty_discount_amount = 0.0

    def apply_loyalty_discount(self):
        """Áp dụng giảm giá thân thiết vào đơn hàng"""
        self.ensure_one()
        if not self.loyalty_discount:
            raise UserError(_("Vui lòng chọn 'Áp dụng giảm giá thân thiết' trước khi áp dụng."))
        
        if self.loyalty_discount_percentage <= 0:
            raise UserError(_("Khách hàng không đủ điều kiện nhận giảm giá thân thiết."))
        
        # Xóa dòng giảm giá cũ (nếu có)
        discount_line = self.order_line.filtered(lambda l: l.name == f'Giảm giá thân thiết ({self.loyalty_discount_percentage}%)')
        if discount_line:
            discount_line.unlink()
            self.loyalty_discount_applied = False
        
        if self.loyalty_discount:
            # Tạo dòng mới cho giảm giá
            discount_product = self.env['product.product'].search([('default_code', '=', 'DISCOUNT')], limit=1)
            if not discount_product:
                # Tạo sản phẩm Discount nếu chưa có
                discount_product = self.env['product.product'].create({
                    'name': 'Discount',
                    'default_code': 'DISCOUNT',
                    'type': 'service',
                    'invoice_policy': 'order',
                    'list_price': 0.0,
                    'taxes_id': False,
                })
            
            # Tính lại giá trị đơn hàng trước khi thêm dòng giảm giá
            amount_untaxed = sum(line.price_subtotal for line in self.order_line)
            
            # Tạo dòng giảm giá mới
            discount_amount = -(amount_untaxed * (self.loyalty_discount_percentage / 100.0))
            discount_line_vals = {
                'name': f'Giảm giá thân thiết ({self.loyalty_discount_percentage}%)',
                'product_id': discount_product.id,
                'product_uom_qty': 1.0,
                'price_unit': discount_amount,
                'order_id': self.id,
                'tax_id': False,
            }
            self.env['sale.order.line'].create(discount_line_vals)
            self.loyalty_discount_applied = True
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Thành công'),
                    'message': _('Đã áp dụng giảm giá thân thiết %s%% cho đơn hàng.') % self.loyalty_discount_percentage,
                    'type': 'success',
                }
            }
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Khi thay đổi khách hàng, cập nhật lại số lượt mua hàng"""
        res = super(SaleOrder, self)._onchange_partner_id()
        self._compute_order_count()
        if self.loyalty_discount_applied:
            # Nếu đã áp dụng giảm giá, nhưng đổi khách hàng thì reset
            discount_line = self.order_line.filtered(lambda l: 'Giảm giá thân thiết' in l.name)
            if discount_line:
                self.update({'order_line': [(2, discount_line.id, 0)]})
            self.loyalty_discount_applied = False
        return res