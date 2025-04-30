# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta


class VietnamPartner(models.Model):
    _inherit = 'res.partner'
    
    # Thông tin ngân hàng
    account_number = fields.Char(string='Số tài khoản')
    bank_name = fields.Char(string='Tên ngân hàng')
    bank_branch = fields.Char(string='Chi nhánh')
    
    # Phân loại khách hàng
    customer_type = fields.Selection([
        ('retail', 'Khách lẻ'),
        ('wholesale', 'Khách sỉ'),
    ], string='Loại khách hàng', default='retail')
    
    # Ngưỡng giảm giá cho khách sỉ
    wholesale_discount_rate = fields.Float(string='Tỷ lệ chiết khấu (%)', default=0.0)
    wholesale_auto_qualify = fields.Boolean(string='Tự động xác định khách sỉ', default=True,
                                           help='Tự động phân loại khách sỉ dựa trên lịch sử mua hàng')
    
    # Thông tin trả góp
    allow_installment = fields.Boolean(string='Cho phép trả góp', default=False)
    installment_term = fields.Integer(string='Kỳ hạn trả góp (tháng)', default=3)
    installment_interest_rate = fields.Float(string='Lãi suất trả góp (%/tháng)', default=1.5)
    credit_limit = fields.Float(string='Hạn mức tín dụng', default=0.0)
    
    # Trường tính toán để xác định có phải đối tác Việt Nam không
    is_vietnam = fields.Boolean(string='Là đối tác Việt Nam', compute='_compute_is_vietnam', store=True)
    
    # Thông tin địa chỉ Việt Nam
    district_id = fields.Many2one('res.district', string='Quận/Huyện')
    ward_id = fields.Many2one('res.ward', string='Phường/Xã')
    
    @api.depends('country_id')
    def _compute_is_vietnam(self):
        for record in self:
            record.is_vietnam = record.country_id.code == 'VN' if record.country_id else False
    
    # Kiểm tra lịch sử mua hàng để tự động phân loại khách hàng sỉ
    # Đánh dấu là @api.model để có thể gọi từ cron
    @api.model
    def _cron_compute_wholesale_status(self):
        partners = self.search([('customer_rank', '>', 0), ('wholesale_auto_qualify', '=', True)])
        for partner in partners:
            partner.compute_wholesale_status()
    
    # Trong Odoo 17.0, không cần @api.multi, tất cả các phương thức đều có thể gọi từ bản ghi
    def compute_wholesale_status(self):
        self.ensure_one()
        if self.wholesale_auto_qualify:
            # Lấy đơn hàng trong 6 tháng gần nhất
            six_months_ago = fields.Date.today() - timedelta(days=180)
            orders = self.env['sale.order'].search([
                ('partner_id', '=', self.id),
                ('date_order', '>=', six_months_ago),
                ('state', 'in', ['sale', 'done'])
            ])
            
            total_amount = sum(order.amount_total for order in orders)
            total_products = sum(sum(line.product_uom_qty for line in order.order_line) for order in orders)
            
            # Tự động phân loại khách sỉ nếu mua hơn 15 triệu hoặc hơn 30 sản phẩm
            if total_amount > 15000000 or total_products > 30:
                self.customer_type = 'wholesale'
                # Thiết lập chiết khấu mặc định nếu chưa có
                if self.wholesale_discount_rate == 0:
                    if total_products > 100:
                        self.wholesale_discount_rate = 20.0
                    elif total_products > 50:
                        self.wholesale_discount_rate = 15.0
                    elif total_products > 30:
                        self.wholesale_discount_rate = 10.0
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thành công'),
                        'message': _('Khách hàng đã được cập nhật thành khách sỉ.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thông báo'),
                        'message': _('Khách hàng không đủ điều kiện để trở thành khách sỉ.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }
    
    # Gửi cảnh báo những hóa đơn chưa thanh toán
    @api.model
    def _cron_check_unpaid_invoices(self):
        today = fields.Date.today()
        one_week_ago = today - timedelta(days=7)
        
        # Tìm các hóa đơn chưa thanh toán quá 1 tuần
        unpaid_invoices = self.env['account.move'].search([
            ('invoice_date', '<=', one_week_ago),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('move_type', '=', 'out_invoice')
        ])
        
        # Gửi thông báo cho từng khách hàng
        for invoice in unpaid_invoices:
            # Tạo message trong chatter
            invoice.message_post(
                body=_('Cảnh báo: Hóa đơn %s đã quá hạn thanh toán 1 tuần.') % invoice.name,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Gửi email thông báo nếu có email khách hàng
            if invoice.partner_id.email:
                template = self.env.ref('vietnam_sale.mail_template_unpaid_invoice_reminder')
                template.send_mail(invoice.id, force_send=True)