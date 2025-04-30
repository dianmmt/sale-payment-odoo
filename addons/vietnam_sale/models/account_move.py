# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class VietnamAccountMove(models.Model):
    _inherit = 'account.move'
    
    vn_invoice_type = fields.Selection([
        ('gtgt', 'Hóa đơn GTGT'),
        ('ban_hang', 'Hóa đơn bán hàng'),
        ('xuat_kho', 'Phiếu xuất kho kiêm vận chuyển nội bộ')
    ], string='Loại hóa đơn', default='gtgt')
    
    is_wholesale = fields.Boolean(string='Hóa đơn bán sỉ', compute='_compute_is_wholesale', store=True)
    e_invoice_number = fields.Char(string='Số hóa đơn điện tử')
    e_invoice_series = fields.Char(string='Ký hiệu hóa đơn')
    e_invoice_date = fields.Date(string='Ngày hóa đơn điện tử')
    e_invoice_status = fields.Selection([
        ('not_created', 'Chưa tạo'),
        ('draft', 'Nháp'),
        ('signed', 'Đã ký'),
        ('sent', 'Đã gửi'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái hóa đơn điện tử', default='not_created')
    payment_method = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('bank_transfer', 'Chuyển khoản'),
        ('credit', 'Công nợ'),
        ('installment', 'Trả góp')
    ], string='Phương thức thanh toán')
    
    @api.depends('partner_id')
    def _compute_is_wholesale(self):
        for move in self:
            move.is_wholesale = move.partner_id.customer_type == 'wholesale'
    
    # Khi tạo hóa đơn từ đơn hàng, lấy các thông tin liên quan
    @api.model
    def create(self, vals):
        move = super(VietnamAccountMove, self).create(vals)
        
        # Nếu được tạo từ đơn bán hàng, lấy thông tin từ đơn
        if move.move_type == 'out_invoice' and move.invoice_origin:
            sale_orders = self.env['sale.order'].search([('name', '=', move.invoice_origin)])
            if sale_orders:
                so = sale_orders[0]
                move.vn_invoice_type = so.vn_invoice_type
                move.payment_method = so.payment_method
        
        return move
    
    # Xuất hóa đơn điện tử
    def action_create_e_invoice(self):
        self.ensure_one()
        if self.move_type != 'out_invoice':
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tạo hóa đơn điện tử'),
            'res_model': 'vietnam.e.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_invoice_date': fields.Date.today()
            }
        }