from odoo import models, fields, api, _
from datetime import timedelta

class VNPaymentReminder(models.Model):
    _name = 'vn.payment.reminder'
    _description = 'Nhắc nhở thanh toán'
    
    @api.model
    def _send_payment_reminders(self):
        # Tìm các kế hoạch trả góp sắp đến hạn (trước 1 tuần) và chưa gửi nhắc nhở
        reminder_date = fields.Date.today() + timedelta(days=7)
        
        plans_to_remind = self.env['vn.sale.installment.plan'].search([
            ('due_date', '=', reminder_date),
            ('state', '=', 'draft'),
            ('reminder_sent', '=', False)
        ])
        
        for plan in plans_to_remind:
            plan.action_send_reminder()
        
        return True