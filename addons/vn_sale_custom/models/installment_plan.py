from odoo import models, fields, api, _
from datetime import timedelta
from odoo.exceptions import UserError

class VNSaleInstallmentPlan(models.Model):
    _name = 'vn.sale.installment.plan'
    _description = 'Kế hoạch trả góp'
    _order = 'installment_number asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True, ondelete='cascade')
    installment_number = fields.Integer(string='Kỳ trả góp', required=True, tracking=True)
    due_date = fields.Date(string='Ngày đến hạn', required=True, tracking=True)
    amount = fields.Float(string='Số tiền', required=True, tracking=True)
    principal_amount = fields.Float(string='Tiền gốc', required=True, tracking=True)
    interest_amount = fields.Float(string='Tiền lãi', required=True, tracking=True)
    remaining_principal = fields.Float(string='Dư nợ còn lại', required=True, tracking=True)
    payment_date = fields.Date(string='Ngày thanh toán', tracking=True)
    state = fields.Selection([
        ('draft', 'Chờ thanh toán'),
        ('invoiced', 'Đã xuất hóa đơn'),
        ('paid', 'Đã thanh toán'),
        ('overdue', 'Quá hạn'),
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    reminder_sent = fields.Boolean(string='Đã gửi nhắc nhở', default=False, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Hóa đơn', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', related='sale_order_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='sale_order_id.currency_id', store=True)
    
    def action_mark_as_paid(self):
        for plan in self:
            if plan.state != 'paid':
                plan.write({
                    'state': 'paid',
                    'payment_date': fields.Date.today(),
                })
                # Gửi thông báo cho người dùng nội bộ
                self._notify_internal_users(f"Khoản thanh toán {plan.installment_number} của đơn hàng {plan.sale_order_id.name} đã được thanh toán")
    
    def action_send_reminder(self):
        for plan in self:
            # Gửi email nhắc nhở cho khách hàng
            template = self.env.ref('vn_sale_custom.mail_template_payment_reminder')
            if template:
                template.send_mail(plan.id, force_send=True)
                
            # Gửi email nhắc nhở cho nhân viên nội bộ
            internal_template = self.env.ref('vn_sale_custom.mail_template_payment_reminder_internal')
            if internal_template:
                internal_template.send_mail(plan.id, force_send=True)
                
            # Gửi thông báo cho người dùng nội bộ
            self._notify_internal_users(f"Đã gửi nhắc nhở thanh toán kỳ {plan.installment_number} cho đơn hàng {plan.sale_order_id.name}")
                
            plan.reminder_sent = True
    
    def _notify_internal_users(self, message):
        """Gửi thông báo cho các người dùng nội bộ"""
        # Lấy người phụ trách và nhóm người dùng bán hàng
        partner_ids = []
            
        # Thêm người phụ trách đơn hàng
        if self.sale_order_id.user_id and self.sale_order_id.user_id.partner_id:
            partner_ids.append(self.sale_order_id.user_id.partner_id.id)
            
        # Thêm các thành viên của nhóm Sales Manager
        sales_manager_group = self.env.ref('sales_team.group_sale_manager')
        if sales_manager_group:
            for user in sales_manager_group.users:
                if user.partner_id:
                    partner_ids.append(user.partner_id.id)
            
        # Gửi thông báo qua chatter
        if partner_ids:
            self.message_post(
                body=message,
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id,
                partner_ids=partner_ids,
            )
    
    def action_create_invoice(self):
        """Tạo hóa đơn cho khoản trả góp này"""
        self.ensure_one()
        
        if self.invoice_id:
            raise UserError(_('Hóa đơn đã được tạo cho khoản trả góp này.'))
        
        if self.state == 'paid':
            raise UserError(_('Không thể tạo hóa đơn cho khoản đã thanh toán.'))
            
        # Lấy thông tin từ đơn hàng
        sale_order = self.sale_order_id
        
        # Tạo hóa đơn mới
        invoice_vals = {
            'partner_id': sale_order.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_origin': f"{sale_order.name} - Trả góp {self.installment_number}",
            'ref': f"{sale_order.name}/INS{self.installment_number}",
            'narration': f"Khoản thanh toán trả góp {self.installment_number} cho đơn hàng {sale_order.name}",
            'currency_id': sale_order.currency_id.id,
            'invoice_payment_term_id': sale_order.payment_term_id.id,
            'invoice_user_id': sale_order.user_id.id,
            'team_id': sale_order.team_id.id,
            'company_id': sale_order.company_id.id,
        }
        
        # Tạo các dòng chi tiết của hóa đơn
        invoice_line_vals = []
        
        # 1. Dòng tiền gốc
        if self.principal_amount > 0:
            principal_line = {
                'name': f"Tiền gốc - Kỳ {self.installment_number}/{sale_order.installment_term_id.months if sale_order.installment_term_id else sale_order.installment_term}",
                'price_unit': self.principal_amount,
                'quantity': 1.0,
                'product_id': self.env.ref('vn_sale_custom.product_installment_principal').id,
                'tax_ids': [(6, 0, self.env.ref('vn_sale_custom.tax_installment_principal').ids)],
            }
            invoice_line_vals.append((0, 0, principal_line))
        
        # 2. Dòng tiền lãi
        if self.interest_amount > 0:
            interest_line = {
                'name': f"Tiền lãi - Kỳ {self.installment_number}/{sale_order.installment_term_id.months if sale_order.installment_term_id else sale_order.installment_term}",
                'price_unit': self.interest_amount,
                'quantity': 1.0,
                'product_id': self.env.ref('vn_sale_custom.product_installment_interest').id,
                'tax_ids': [(6, 0, self.env.ref('vn_sale_custom.tax_installment_interest').ids)],
            }
            invoice_line_vals.append((0, 0, interest_line))
        
        invoice_vals['invoice_line_ids'] = invoice_line_vals
        
        # Tạo hóa đơn
        invoice = self.env['account.move'].create(invoice_vals)
        self.write({
            'invoice_id': invoice.id,
            'state': 'invoiced'
        })
        
        # Mở hóa đơn để xem
        return {
            'name': _('Hóa đơn trả góp'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }
    
    @api.model
    def check_overdue_installments(self):
        """Kiểm tra và cập nhật các khoản trả góp quá hạn"""
        today = fields.Date.today()
        overdue_plans = self.search([
            ('state', '=', 'draft'),
            ('due_date', '<', today)
        ])
        
        if overdue_plans:
            overdue_plans.write({'state': 'overdue'})
            
            # Tự động gửi email nhắc nhở
            for plan in overdue_plans:
                if not plan.reminder_sent:
                    plan.action_send_reminder()
    @api.model
    def _send_payment_reminders(self):
        """Tự động gửi nhắc nhở cho các khoản trả góp sắp đến hạn"""
        today = fields.Date.today()
        # Các khoản đến hạn trong 3 ngày tới
        upcoming_due_date = today + timedelta(days=3)
        
        upcoming_plans = self.search([
            ('state', '=', 'draft'),
            ('due_date', '<=', upcoming_due_date),
            ('due_date', '>=', today),
            ('reminder_sent', '=', False)
        ])
        
        for plan in upcoming_plans:
            # Gửi email nhắc nhở
            plan.action_send_reminder()
    def action_view_invoice(self):
        """Mở hóa đơn để xem"""
        self.ensure_one()
        if not self.invoice_id:
            return
            
        return {
            'name': _('Hóa đơn trả góp'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'type': 'ir.actions.act_window',
        }