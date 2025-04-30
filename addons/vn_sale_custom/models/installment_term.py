from odoo import models, fields, api, _

class VNSaleInstallmentTerm(models.Model):
    _name = 'vn.sale.installment.term'
    _description = 'Kỳ hạn trả góp'
    _order = 'months asc'
    
    name = fields.Char(string='Tên', required=True)
    months = fields.Integer(string='Số tháng', required=True)
    annual_interest_rate = fields.Float(string='Lãi suất năm (%)', required=True)
    monthly_interest_rate = fields.Float(string='Lãi suất tháng (%)', compute='_compute_monthly_interest_rate', store=True)
    active = fields.Boolean(default=True)
    
    @api.depends('annual_interest_rate')
    def _compute_monthly_interest_rate(self):
        for term in self:
            term.monthly_interest_rate = term.annual_interest_rate / 12
    
    