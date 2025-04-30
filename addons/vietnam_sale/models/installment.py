# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta

class VietnamSaleInstallmentSchedule(models.Model):
    _name = 'vietnam.sale.installment.schedule'
    _description = 'Vietnam Sale Installment Schedule'
    _order = 'payment_date'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    payment_date = fields.Date(string='Payment Date')
    month_number = fields.Integer(string='Month Number')
    principal_amount = fields.Monetary(string='Principal Amount')
    interest_amount = fields.Monetary(string='Interest Amount')
    total_amount = fields.Monetary(string='Total Amount')
    remaining_amount = fields.Monetary(string='Remaining Amount')
    actual_payment_date = fields.Date(string='Actual Payment Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('paid', 'Paid'),
        ('late', 'Late'),
        ('partial', 'Partial'),
    ], string='Status', default='draft')
    note = fields.Text(string='Note')
    currency_id = fields.Many2one('res.currency', string='Currency')
    is_due_soon = fields.Boolean(
        string='Due Soon',
        compute='_compute_is_due_soon',
        store=False
    )

    @api.depends('payment_date')
    def _compute_is_due_soon(self):
        today = fields.Date.context_today(self)
        due_soon_date = today + timedelta(days=7)
        for record in self:
            if record.payment_date:
                record.is_due_soon = today <= record.payment_date <= due_soon_date
            else:
                record.is_due_soon = False

    @api.model
    def _cron_update_installment_status(self):
        today = fields.Date.today()
        due_schedules = self.search([
            ('payment_date', '<', today),
            ('state', '=', 'draft')
        ])
        for schedule in due_schedules:
            schedule.state = 'late'
            schedule.sale_order_id.message_post(
                body=_('Installment %s of order %s is overdue.') % 
                     (schedule.month_number, schedule.sale_order_id.name),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )

    def action_confirm_payment(self):
        self.ensure_one()
        self.write({
            'state': 'paid',
            'actual_payment_date': fields.Date.today()
        })
        all_paid = all(s.state == 'paid' for s in self.sale_order_id.installment_schedule_ids)
        if all_paid:
            self.sale_order_id.message_post(
                body=_('All installments have been fully paid.'),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
        return True

    def action_partial_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partial Payment'),
            'res_model': 'vietnam.installment.partial.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_installment_id': self.id}
        }