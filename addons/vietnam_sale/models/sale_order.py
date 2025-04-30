# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class VietnamSaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # Thông tin hóa đơn và xuất hóa đơn
    vn_invoice_type = fields.Selection([
        ('gtgt', 'Hóa đơn GTGT'),
        ('ban_hang', 'Hóa đơn bán hàng'),
        ('xuat_kho', 'Phiếu xuất kho kiêm vận chuyển nội bộ')
    ], string='Loại hóa đơn', default='gtgt')
    
    # Phương thức thanh toán
    payment_method = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('bank_transfer', 'Chuyển khoản'),
        ('credit', 'Công nợ'),
        ('installment', 'Trả góp')
    ], string='Phương thức thanh toán', default='bank_transfer')
    
    # Thông tin thuế và giá
    vat_inclusive = fields.Boolean(string='Giá đã bao gồm VAT', default=False)
    
    # Thông tin khách hàng
    buyer_tax_code = fields.Char(string='Mã số thuế', related='partner_id.vat', readonly=False)
    buyer_representative = fields.Char(string='Người đại diện')
    
    # Thông tin xuất hóa đơn điện tử
    need_invoice = fields.Boolean(string='Yêu cầu xuất hóa đơn', default=True)
    e_invoice_status = fields.Selection([
        ('not_created', 'Chưa tạo'),
        ('draft', 'Nháp'),
        ('signed', 'Đã ký'),
        ('sent', 'Đã gửi'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái hóa đơn điện tử', default='not_created')
    
    # Thông tin khách hàng sỉ
    customer_type = fields.Selection(related='partner_id.customer_type', string='Loại khách hàng', readonly=True)
    is_wholesale = fields.Boolean(
        string='Đơn hàng sỉ', 
        compute='_compute_is_wholesale', 
        store=True
    )
    wholesale_discount = fields.Float(string='Chiết khấu khách sỉ (%)', default=0.0)
    was_converted_to_wholesale = fields.Boolean(
        string='Đã chuyển thành đơn sỉ', 
        default=False,
        help='Đánh dấu đơn hàng đã được tự động chuyển thành đơn sỉ'
    )
    
    # Thông tin trả góp
    installment_months = fields.Integer(string='Số tháng trả góp', default=3)
    installment_interest = fields.Float(string='Lãi suất (%/tháng)', default=1.5)
    installment_amount = fields.Float(
        string='Số tiền trả mỗi tháng', 
        compute='_compute_installment_amount'
    )
    installment_schedule_ids = fields.One2many(
        'vietnam.sale.installment.schedule', 
        'sale_order_id', 
        string='Lịch trả góp'
    )
    
    # Thông tin báo giá
    quotation_type = fields.Selection([
        ('normal', 'Thông thường'),
        ('wholesale', 'Báo giá sỉ')
    ], string='Loại báo giá', default='normal')
    
    # Tổng số lượng sản phẩm
    total_product_quantity = fields.Float(
        string='Tổng số lượng sản phẩm', 
        compute='_compute_total_product_quantity', 
        store=True
    )
    
    @api.depends('order_line.product_uom_qty')
    def _compute_total_product_quantity(self):
        for order in self:
            order.total_product_quantity = sum(order.order_line.mapped('product_uom_qty'))
    
    @api.depends('partner_id', 'total_product_quantity', 'amount_total', 'order_line.product_uom_qty')
    def _compute_is_wholesale(self):
        for order in self:
            # Kiểm tra trạng thái khách hàng sỉ
            old_is_wholesale = order.is_wholesale
            
            # Kiểm tra xem khách hàng đã được đánh dấu là khách sỉ chưa
            if order.partner_id.customer_type == 'wholesale':
                order.is_wholesale = True
            else:
                # Kiểm tra các điều kiện để xác định đơn hàng sỉ
                order.is_wholesale = (
                    order.total_product_quantity > 30 or 
                    order.amount_total > 15000000
                )
            
            # Xử lý khi chuyển thành đơn sỉ
            if order.is_wholesale and not old_is_wholesale and not order.was_converted_to_wholesale:
                order.was_converted_to_wholesale = True
                
                # Ghi log thay vì sử dụng message_post
                messages = []
                if order.total_product_quantity > 30:
                    messages.append(
                        f'Số lượng sản phẩm ({order.total_product_quantity}) vượt quá 30.'
                    )
                if order.amount_total > 15000000:
                    messages.append(
                        f'Giá trị đơn hàng ({order.amount_total}) vượt quá 15 triệu đồng.'
                    )
                
                # Áp dụng chiết khấu
                if order.wholesale_discount == 0:
                    if order.total_product_quantity > 100:
                        order.wholesale_discount = 0
                    elif order.total_product_quantity > 50:
                        order.wholesale_discount = 15.0
                    elif order.total_product_quantity > 30:
                        order.wholesale_discount = 10.0
    
    @api.depends('amount_total', 'installment_months', 'installment_interest')
    def _compute_installment_amount(self):
        for order in self:
            if order.payment_method == 'installment' and order.installment_months > 0:
                # Tính toán số tiền trả góp
                principal_per_month = order.amount_total / order.installment_months
                interest_first_month = order.amount_total * (order.installment_interest / 100)
                order.installment_amount = round(principal_per_month + interest_first_month, -3)
            else:
                order.installment_amount = 0.0
    
    def generate_installment_schedule(self):
        """Tạo lịch trả góp chi tiết"""
        self.ensure_one()
        if self.payment_method != 'installment':
            return
        
        # Xóa lịch trả góp cũ
        self.installment_schedule_ids.unlink()
        
        # Tính toán lịch trả góp
        principal_per_month = self.amount_total / self.installment_months
        remaining_amount = self.amount_total
        
        for month in range(1, self.installment_months + 1):
            # Tính lãi và số tiền còn lại
            interest = remaining_amount * (self.installment_interest / 100)
            remaining_amount -= principal_per_month
            
            # Tạo bản ghi lịch trả góp
            self.env['vietnam.sale.installment.schedule'].create({
                'sale_order_id': self.id,
                'payment_date': fields.Date.today() + timedelta(days=30 * month),
                'month_number': month,
                'principal_amount': principal_per_month,
                'interest_amount': interest,
                'total_amount': principal_per_month + interest,
                'remaining_amount': max(remaining_amount, 0),
                'state': 'draft'
            })
        
        return True
    
    def apply_wholesale_discount(self):
        """Áp dụng chiết khấu cho khách sỉ"""
        for order in self:
            if not order.is_wholesale or not order.wholesale_discount:
                continue
            
            # Áp dụng chiết khấu cho các dòng sản phẩm
            for line in order.order_line:
                line.discount = order.wholesale_discount
        
        return True
    
    @api.depends('order_line.price_total', 'vat_inclusive')
    def _amount_all(self):
        """Tính toán giá trị đơn hàng"""
        super(VietnamSaleOrder, self)._amount_all()
        for order in self:
            if order.vat_inclusive:
                amount_untaxed = sum(line.price_subtotal for line in order.order_line)
                amount_tax = sum(line.price_tax for line in order.order_line)
                order.update({
                    'amount_untaxed': amount_untaxed,
                    'amount_tax': amount_tax,
                    'amount_total': amount_untaxed + amount_tax,
                })
    
    def action_confirm(self):
        """Xử lý khi xác nhận đơn hàng"""
        res = super(VietnamSaleOrder, self).action_confirm()
        
        for order in self:
            # Tạo lịch trả góp nếu là đơn trả góp
            if order.payment_method == 'installment':
                order.generate_installment_schedule()
            
            # Cập nhật thông tin khách hàng sỉ
            if order.is_wholesale and order.partner_id.customer_type != 'wholesale':
                order.partner_id.write({
                    'customer_type': 'wholesale',
                    'wholesale_discount_rate': order.wholesale_discount
                })
        
        return res
    
    def action_create_e_invoice(self):
        """Tạo hóa đơn điện tử"""
        self.ensure_one()
        if not self.partner_id.vat and self.need_invoice:
            raise ValidationError(_('Vui lòng cung cấp mã số thuế của khách hàng để xuất hóa đơn.'))
        
        self.e_invoice_status = 'draft'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo hóa đơn điện tử'),
            'res_model': 'vietnam.e.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id}
        }
    
    def action_create_wholesale_quotation(self):
        """Tạo báo giá sỉ"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo báo giá sỉ'),
            'res_model': 'vietnam.wholesale.quotation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_total_quantity': self.total_product_quantity,
                'default_discount_rate': self.wholesale_discount or 0.0
            }
        }


class VietnamSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    # Đơn vị tính sản phẩm
    vn_product_unit = fields.Char(
        string='Đơn vị tính', 
        related='product_id.vn_product_unit', 
        readonly=False
    )
    
    # Thuế suất GTGT
    vn_vat_rate = fields.Selection([
        ('0', '0%'),
        ('5', '5%'),
        ('8', '8%'),
        ('10', '10%'),
        ('exempt', 'Không chịu thuế')
    ], string='Thuế suất GTGT', default='10')
    
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'vn_vat_rate')
    def _compute_amount(self):
        """Tính toán giá trị dòng sản phẩm"""
        super(VietnamSaleOrderLine, self)._compute_amount()
        for line in self:
            if line.order_id.vat_inclusive and line.vn_vat_rate != 'exempt':
                # Tính toán giá trị không bao gồm thuế
                vat_rate = float(line.vn_vat_rate or '0') / 100
                price_unit_no_vat = line.price_unit / (1 + vat_rate)
                
                # Tính toán giá và thuế
                price = price_unit_no_vat * (1 - (line.discount or 0.0) / 100.0)
                taxes = line.tax_id.compute_all(
                    price, 
                    line.order_id.currency_id, 
                    line.product_uom_qty, 
                    product=line.product_id, 
                    partner=line.order_id.partner_shipping_id
                )
                
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })