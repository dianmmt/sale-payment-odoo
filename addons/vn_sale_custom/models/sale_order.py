from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

class VNSaleOrder(models.Model):
    _inherit = 'sale.order'
    
    is_installment = fields.Boolean(string='Thanh toán trả góp', default=False)
    
    # Giữ trường cũ cho tương thích ngược
    installment_term = fields.Selection([
        ('3', '3 tháng'),
        ('6', '6 tháng'),
        ('12', '12 tháng'),
        ('24', '24 tháng'),
        ('48', '48 tháng'),
    ], string='Kỳ hạn trả góp (cũ)')
    
    # Thêm trường mới
    installment_term_id = fields.Many2one('vn.sale.installment.term', string='Kỳ hạn trả góp')
    
    # Thêm trường cho phép nhập lãi suất thủ công
    interest_rate_custom = fields.Float(string='Lãi suất tháng tùy chỉnh (%)')
    interest_rate = fields.Float(string='Lãi suất năm (%)', compute='_compute_interest_rate', store=True)
    monthly_interest_rate = fields.Float(string='Lãi suất tháng (%)', compute='_compute_interest_rate', store=True)
    
    # Thêm trường cho thuế GTGT 10%
    amount_vat = fields.Monetary(string='Thuế GTGT (10%)', compute='_compute_amount_vat', store=True)
    amount_with_vat = fields.Monetary(string='Tổng tiền (bao gồm VAT)', compute='_compute_amount_with_vat', store=True)
    total_with_interest = fields.Monetary(string='Tổng tiền (bao gồm VAT và lãi)', compute='_compute_total_with_interest', store=True)
    monthly_payment = fields.Monetary(string='Thanh toán hàng tháng', compute='_compute_monthly_payment', store=True)
    installment_plan_ids = fields.One2many('vn.sale.installment.plan', 'sale_order_id', string='Kế hoạch trả góp')
    
    @api.onchange('installment_term')
    def _onchange_installment_term(self):
        if self.installment_term and not self.installment_term_id:
            # Tìm kỳ hạn tương ứng
            months = int(self.installment_term)
            term = self.env['vn.sale.installment.term'].search([('months', '=', months)], limit=1)
            if term:
                self.installment_term_id = term.id

    @api.onchange('installment_term_id')
    def _onchange_installment_term_id(self):
        if self.installment_term_id and not self.installment_term:
            # Cập nhật trường cũ để tương thích
            if str(self.installment_term_id.months) in dict(self._fields['installment_term'].selection):
                self.installment_term = str(self.installment_term_id.months)
    
    @api.depends('installment_term_id', 'installment_term', 'interest_rate_custom')
    def _compute_interest_rate(self):
        for order in self:
            if not order.is_installment:
                order.interest_rate = 0.0
                order.monthly_interest_rate = 0.0
                continue
                
            # Ưu tiên sử dụng trường mới
            if order.installment_term_id:
                if order.interest_rate_custom > 0:
                    order.monthly_interest_rate = order.interest_rate_custom
                    order.interest_rate = order.interest_rate_custom * 12
                else:
                    order.interest_rate = order.installment_term_id.annual_interest_rate
                    order.monthly_interest_rate = order.installment_term_id.monthly_interest_rate
            else:
                # Dùng trường cũ nếu trường mới chưa có dữ liệu
                if not order.installment_term:
                    order.interest_rate = 0.0
                    order.monthly_interest_rate = 0.0
                    continue
                    
                if order.interest_rate_custom > 0:
                    order.monthly_interest_rate = order.interest_rate_custom
                    order.interest_rate = order.interest_rate_custom * 12
                else:
                    # Sử dụng lãi suất mặc định dựa trên kỳ hạn (lãi suất năm)
                    term_rates = {
                        '3': 10.0,   # 10% cho 3 tháng
                        '6': 12.0,   # 12% cho 6 tháng
                        '12': 15.0,  # 15% cho 12 tháng
                        '24': 18.0,  # 18% cho 24 tháng
                        '48': 22.0,  # 22% cho 48 tháng
                    }
                    order.interest_rate = term_rates.get(order.installment_term, 0.0)
                    order.monthly_interest_rate = order.interest_rate / 12
    
    @api.depends('amount_untaxed')
    def _compute_amount_vat(self):
        for order in self:
            # Tính thuế GTGT 10% dựa trên tổng tiền hàng không bao gồm thuế
            order.amount_vat = order.amount_untaxed * 0.1
    
    @api.depends('amount_untaxed', 'amount_vat')
    def _compute_amount_with_vat(self):
        for order in self:
            # Tổng tiền bao gồm thuế GTGT
            order.amount_with_vat = order.amount_untaxed + order.amount_vat
    
    @api.depends('amount_with_vat', 'is_installment', 'installment_term_id', 'installment_term', 'monthly_interest_rate')
    def _compute_total_with_interest(self):
        for order in self:
            if not order.is_installment or (not order.installment_term_id and not order.installment_term) or not order.monthly_interest_rate:
                order.total_with_interest = order.amount_with_vat
                continue
                
            # Tính tổng tiền bao gồm lãi
            term_months = order.installment_term_id.months if order.installment_term_id else int(order.installment_term)
            monthly_rate = order.monthly_interest_rate / 100
            
            # Công thức tính tổng tiền với lãi suất
            principal = order.amount_with_vat  # Sử dụng tổng tiền đã bao gồm VAT
            total_interest = principal * monthly_rate * term_months
            order.total_with_interest = principal + total_interest
    
    @api.depends('total_with_interest', 'installment_term_id', 'installment_term')
    def _compute_monthly_payment(self):
        for order in self:
            if not order.is_installment or (not order.installment_term_id and not order.installment_term):
                order.monthly_payment = 0.0
                continue
                
            term_months = order.installment_term_id.months if order.installment_term_id else int(order.installment_term)
            order.monthly_payment = order.total_with_interest / term_months
    
    def action_confirm(self):
        res = super(VNSaleOrder, self).action_confirm()
        for order in self:
            if order.is_installment and (order.installment_term_id or order.installment_term):
                # Tạo kế hoạch trả góp khi xác nhận đơn hàng
                self._create_installment_plan()
        return res
    
    def _create_installment_plan(self):
        self.ensure_one()
        if not self.is_installment:
            return
            
        if not self.installment_term_id and not self.installment_term:
            return
                
        # Xóa kế hoạch trả góp cũ (nếu có)
        self.installment_plan_ids.unlink()
        
        # Ưu tiên sử dụng trường mới
        term_months = self.installment_term_id.months if self.installment_term_id else int(self.installment_term)
        installment_plan_vals = []
        
        # Tạo kế hoạch trả góp
        for i in range(1, term_months + 1):
            due_date = fields.Date.today() + timedelta(days=30 * i)
            installment_plan_vals.append({
                'sale_order_id': self.id,
                'installment_number': i,
                'due_date': due_date,
                'amount': self.monthly_payment,
                'state': 'draft',
            })
        
        # Tạo các bản ghi kế hoạch trả góp
        self.env['vn.sale.installment.plan'].create(installment_plan_vals)