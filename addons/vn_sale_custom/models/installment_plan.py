from odoo import models, fields, api, _
from datetime import timedelta

class VNSaleInstallmentPlan(models.Model):
    _name = 'vn.sale.installment.plan'
    _description = 'Kế hoạch trả góp'
    _order = 'installment_number asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True, ondelete='cascade')
    installment_number = fields.Integer(string='Kỳ trả góp', required=True, tracking=True)
    due_date = fields.Date(string='Ngày đến hạn', required=True, tracking=True)
    amount = fields.Float(string='Số tiền', required=True, tracking=True)
    payment_date = fields.Date(string='Ngày thanh toán', tracking=True)
    state = fields.Selection([
        ('draft', 'Chờ thanh toán'),
        ('paid', 'Đã thanh toán'),
        ('overdue', 'Quá hạn'),
    ], string='Trạng thái', default='draft', required=True, tracking=True)
    reminder_sent = fields.Boolean(string='Đã gửi nhắc nhở', default=False, tracking=True)
    
    def action_mark_as_paid(self):
        for plan in self:
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