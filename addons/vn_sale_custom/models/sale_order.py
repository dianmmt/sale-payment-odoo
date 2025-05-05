from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import math

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
    
    # Chỉ sử dụng lãi suất năm
    interest_rate = fields.Float(string='Lãi suất năm (%)', compute='_compute_interest_rate', store=True)
    
    # Thêm trường cho thuế GTGT 10%
    amount_vat = fields.Monetary(string='Thuế GTGT (10%)', compute='_compute_amount_all', store=True)
    # Thay đổi computation methods
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_compute_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_compute_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_amount_all', tracking=True)
    
    # Thêm lại trường tổng tiền sau khi tính lãi
    total_with_interest = fields.Monetary(string='Tổng tiền (bao gồm lãi)', compute='_compute_total_with_interest', store=True)
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
    
    @api.depends('installment_term_id', 'installment_term')
    def _compute_interest_rate(self):
        for order in self:
            if not order.is_installment:
                order.interest_rate = 0.0
                continue
                
            # Ưu tiên sử dụng trường mới
            if order.installment_term_id:
                order.interest_rate = order.installment_term_id.annual_interest_rate
            else:
                # Dùng trường cũ nếu trường mới chưa có dữ liệu
                if not order.installment_term:
                    order.interest_rate = 0.0
                    continue
                    
                # Sử dụng lãi suất mặc định dựa trên kỳ hạn (lãi suất năm)
                term_rates = {
                    '3': 10.0,   # 10% cho 3 tháng
                    '6': 12.0,   # 12% cho 6 tháng
                    '12': 15.0,  # 15% cho 12 tháng
                    '24': 18.0,  # 18% cho 24 tháng
                    '48': 22.0,  # 22% cho 48 tháng
                }
                order.interest_rate = term_rates.get(order.installment_term, 0.0)
    
    @api.depends('order_line.price_total')
    def _compute_amount_all(self):
        """
        Tính lại tổng tiền bao gồm thuế
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            
            # Đặt giá trị
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_vat': amount_tax,  # Giữ cả 2 trường để tương thích
                'amount_total': amount_untaxed + amount_tax,
            })
    
    @api.depends('amount_total', 'is_installment', 'installment_term_id', 'installment_term', 'interest_rate')
    def _compute_total_with_interest(self):
        for order in self:
            if not order.is_installment or (not order.installment_term_id and not order.installment_term) or not order.interest_rate:
                order.total_with_interest = order.amount_total
                continue
                
            # Tính tổng tiền bao gồm lãi theo phương pháp giảm dần (reducing balance)
            term_months = order.installment_term_id.months if order.installment_term_id else int(order.installment_term)
            annual_rate = order.interest_rate / 100  # Chuyển từ % năm sang tỷ lệ năm
            monthly_rate = annual_rate / 12  # Chuyển từ lãi suất năm sang lãi suất tháng
            
            # Công thức tính tổng tiền với lãi suất giảm dần (EMI - Equated Monthly Installment)
            principal = order.amount_total  # Sử dụng tổng tiền đã bao gồm VAT
            
            # Công thức EMI = P * r * (1+r)^n / ((1+r)^n - 1)
            # Trong đó P là tiền gốc, r là lãi suất tháng, n là số tháng
            if monthly_rate > 0:
                emi = principal * monthly_rate * math.pow(1 + monthly_rate, term_months) / (math.pow(1 + monthly_rate, term_months) - 1)
                total_payment = emi * term_months
            else:
                # Nếu lãi suất là 0
                total_payment = principal
                
            order.total_with_interest = total_payment
    
    @api.depends('total_with_interest', 'installment_term_id', 'installment_term')
    def _compute_monthly_payment(self):
        for order in self:
            if not order.is_installment or (not order.installment_term_id and not order.installment_term):
                order.monthly_payment = 0.0
                continue
                
            term_months = order.installment_term_id.months if order.installment_term_id else int(order.installment_term)
            
            # Tính trực tiếp EMI
            principal = order.amount_total
            annual_rate = order.interest_rate / 100
            monthly_rate = annual_rate / 12  # Chuyển từ lãi suất năm sang lãi suất tháng
            
            if monthly_rate > 0:
                emi = principal * monthly_rate * math.pow(1 + monthly_rate, term_months) / (math.pow(1 + monthly_rate, term_months) - 1)
            else:
                # Nếu lãi suất là 0
                emi = principal / term_months
                
            order.monthly_payment = emi
    
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
        
        # Tính lại kế hoạch trả góp chi tiết với phương pháp giảm dần
        principal = self.amount_total
        annual_rate = self.interest_rate / 100
        monthly_rate = annual_rate / 12  # Chuyển từ lãi suất năm sang lãi suất tháng
        
        if monthly_rate > 0:
            emi = principal * monthly_rate * math.pow(1 + monthly_rate, term_months) / (math.pow(1 + monthly_rate, term_months) - 1)
        else:
            emi = principal / term_months
            
        # Tạo kế hoạch trả góp
        remaining_principal = principal
        for i in range(1, term_months + 1):
            due_date = fields.Date.today() + timedelta(days=30 * i)
            
            # Tính lãi và gốc cho kỳ này
            interest_payment = remaining_principal * monthly_rate
            principal_payment = emi - interest_payment
            
            # Cập nhật số dư
            remaining_principal -= principal_payment
            
            # Làm tròn số dư còn lại để tránh lỗi làm tròn
            if i == term_months:
                remaining_principal = 0
            
            installment_plan_vals.append({
                'sale_order_id': self.id,
                'installment_number': i,
                'due_date': due_date,
                'amount': emi,
                'principal_amount': principal_payment,
                'interest_amount': interest_payment,
                'remaining_principal': remaining_principal,
                'state': 'draft',
            })
        
        # Tạo các bản ghi kế hoạch trả góp
        self.env['vn.sale.installment.plan'].create(installment_plan_vals)
    def action_create_all_installment_invoices(self):
        """Tạo hóa đơn cho tất cả các khoản trả góp chưa thanh toán"""
        self.ensure_one()
        
        if not self.is_installment:
            raise UserError(_('Đơn hàng này không phải thanh toán trả góp.'))
        
        pending_plans = self.installment_plan_ids.filtered(lambda p: p.state == 'draft')
        
        if not pending_plans:
            raise UserError(_('Không có khoản trả góp nào chờ thanh toán.'))
        
        # Tạo hóa đơn cho từng khoản trả góp
        for plan in pending_plans:
            plan.action_create_invoice()
        
        return {
            'name': _('Hóa đơn trả góp'),
            'domain': [('id', 'in', pending_plans.mapped('invoice_id').ids)],
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
        }