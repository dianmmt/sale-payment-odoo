# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class WholesaleQuotationWizard(models.TransientModel):
    _name = 'vietnam.wholesale.quotation.wizard'
    _description = 'Wizard tạo báo giá sỉ'
    
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True)
    customer_type = fields.Selection(related='partner_id.customer_type', string='Loại khách hàng')
    product_ids = fields.Many2many('product.product', string='Sản phẩm')
    total_quantity = fields.Float(string='Tổng số lượng', default=0.0)
    discount_rate = fields.Float(string='Tỷ lệ chiết khấu (%)', default=0.0)
    special_price = fields.Boolean(string='Giá đặc biệt', default=False)
    sale_person_id = fields.Many2one('res.users', string='Nhân viên bán hàng', default=lambda self: self.env.user.id)
    
    # Lịch sử mua hàng
    show_purchase_history = fields.Boolean(string='Hiển thị lịch sử mua hàng', default=True)
    purchase_history_ids = fields.Many2many('sale.order', string='Lịch sử mua hàng', compute='_compute_purchase_history')
    total_purchased_amount = fields.Float(string='Tổng giá trị đã mua', compute='_compute_purchase_history')
    total_purchased_quantity = fields.Float(string='Tổng số lượng đã mua', compute='_compute_purchase_history')
    
    @api.depends('partner_id')
    def _compute_purchase_history(self):
        for wizard in self:
            if wizard.partner_id:
                # Lấy đơn hàng trong 12 tháng gần nhất
                orders = self.env['sale.order'].search([
                    ('partner_id', '=', wizard.partner_id.id),
                    ('state', 'in', ['sale', 'done']),
                    ('date_order', '>=', fields.Date.today() - fields.date_utils.relativedelta(months=12))
                ], order='date_order desc', limit=10)
                
                wizard.purchase_history_ids = orders
                wizard.total_purchased_amount = sum(orders.mapped('amount_total'))
                wizard.total_purchased_quantity = sum(
                    sum(line.product_uom_qty for line in order.order_line) for order in orders
                )
            else:
                wizard.purchase_history_ids = False
                wizard.total_purchased_amount = 0.0
                wizard.total_purchased_quantity = 0.0
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            # Nếu là khách sỉ, lấy tỷ lệ chiết khấu từ hồ sơ khách hàng
            if self.partner_id.customer_type == 'wholesale':
                self.discount_rate = self.partner_id.wholesale_discount_rate
    
    @api.onchange('total_quantity')
    def _onchange_total_quantity(self):
        if self.total_quantity > 100:
            self.special_price = True
            self.discount_rate = 0.0
        elif self.total_quantity > 50:
            self.discount_rate = 15.0
            self.special_price = False
        elif self.total_quantity > 30:
            self.discount_rate = 10.0
            self.special_price = False
        else:
            # Nếu là khách sỉ, giữ nguyên tỷ lệ chiết khấu của khách hàng
            if self.partner_id.customer_type == 'wholesale':
                self.discount_rate = self.partner_id.wholesale_discount_rate
            else:
                self.discount_rate = 0.0
            self.special_price = False
    
    def action_create_quotation(self):
        self.ensure_one()
        
        # Tạo đơn báo giá mới
        quotation_vals = {
            'partner_id': self.partner_id.id,
            'user_id': self.sale_person_id.id,
            'quotation_type': 'wholesale',
            'wholesale_discount': self.discount_rate,
            'is_wholesale': True
        }
        
        # Nếu khách hàng chưa được đánh dấu là khách sỉ, cập nhật trạng thái
        if self.partner_id.customer_type != 'wholesale' and self.total_quantity > 30:
            self.partner_id.write({
                'customer_type': 'wholesale',
                'wholesale_discount_rate': self.discount_rate
            })
        
        quotation = self.env['sale.order'].create(quotation_vals)
        
        # Thêm các sản phẩm vào báo giá
        if self.product_ids:
            for product in self.product_ids:
                # Tính giá sau khi áp dụng chiết khấu
                price_unit = product.list_price
                if self.discount_rate > 0:
                    price_unit = price_unit * (1 - self.discount_rate / 100)
                
                self.env['sale.order.line'].create({
                    'order_id': quotation.id,
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': price_unit,
                })
        
        # Nếu là báo giá đặc biệt, thêm ghi chú
        if self.special_price:
            quotation.message_post(
                body=_('Báo giá đặc biệt cho khách hàng sỉ (>100 sản phẩm). Vui lòng liên hệ trực tiếp để thỏa thuận giá.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        
        # Mở báo giá vừa tạo
        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo giá sỉ'),
            'res_model': 'sale.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
        }


class InstallmentPartialPaymentWizard(models.TransientModel):
    _name = 'vietnam.installment.partial.payment.wizard'
    _description = 'Wizard thanh toán một phần kỳ trả góp'
    
    installment_id = fields.Many2one('vietnam.sale.installment.schedule', string='Kỳ trả góp', required=True)
    payment_amount = fields.Float(string='Số tiền thanh toán', required=True)
    payment_date = fields.Date(string='Ngày thanh toán', default=fields.Date.context_today, required=True)
    note = fields.Text(string='Ghi chú')
    
    @api.onchange('installment_id')
    def _onchange_installment_id(self):
        if self.installment_id:
            self.payment_amount = self.installment_id.total_amount
    
    def action_confirm_partial_payment(self):
        self.ensure_one()
        
        # Kiểm tra số tiền thanh toán
        if self.payment_amount <= 0:
            return {
                'warning': {
                    'title': _('Cảnh báo'),
                    'message': _('Số tiền thanh toán phải lớn hơn 0.')
                }
            }
        
        if self.payment_amount >= self.installment_id.total_amount:
            # Nếu thanh toán đủ hoặc nhiều hơn, đánh dấu là đã thanh toán
            self.installment_id.write({
                'state': 'paid',
                'actual_payment_date': self.payment_date,
                'note': self.note
            })
        else:
            # Nếu thanh toán một phần, cập nhật trạng thái
            self.installment_id.write({
                'state': 'partial',
                'actual_payment_date': self.payment_date,
                'note': _('Thanh toán một phần: %s. %s') % (
                    self.env.company.currency_id.symbol + ' {:,.0f}'.format(self.payment_amount),
                    self.note or ''
                )
            })
        
        return {'type': 'ir.actions.act_window_close'}