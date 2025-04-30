# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EInvoiceWizard(models.TransientModel):
    _name = 'vietnam.e.invoice.wizard'
    _description = 'Wizard tạo hóa đơn điện tử'
    
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng')
    invoice_id = fields.Many2one('account.move', string='Hóa đơn')
    e_invoice_provider = fields.Selection([
        ('vnpt', 'VNPT Invoice'),
        ('viettel', 'Viettel E-Invoice'),
        ('fpt', 'FPT E-Invoice')
    ], string='Nhà cung cấp hóa đơn điện tử', default='vnpt')
    invoice_date = fields.Date(string='Ngày hóa đơn', default=fields.Date.context_today)
    invoice_series = fields.Char(string='Ký hiệu hóa đơn')
    invoice_number = fields.Char(string='Số hóa đơn')
    
    # Các trường mở rộng theo yêu cầu HĐĐT Việt Nam
    lookup_invoice_status = fields.Boolean(string='Kiểm tra trạng thái trên cổng thuế', default=False)
    include_payment_info = fields.Boolean(string='Bao gồm thông tin thanh toán', default=True)
    auto_send_email = fields.Boolean(string='Tự động gửi email', default=True)
    
    @api.model
    def default_get(self, fields):
        res = super(EInvoiceWizard, self).default_get(fields)
        
        # Lấy thông tin cấu hình mặc định từ công ty
        company = self.env.company
        res.update({
            'e_invoice_provider': company.e_invoice_provider if hasattr(company, 'e_invoice_provider') else 'vnpt',
            'invoice_series': company.e_invoice_series if hasattr(company, 'e_invoice_series') else False
        })
        
        return res
    
    def action_sign_and_send(self):
        self.ensure_one()
        
        # Xác định đối tượng cần cập nhật (đơn hàng hoặc hóa đơn)
        record = self.sale_order_id or self.invoice_id
        if not record:
            raise ValidationError(_('Không tìm thấy đơn hàng hoặc hóa đơn liên kết.'))
        
        # Kiểm tra thông tin bắt buộc
        if not record.partner_id.vat and record.vn_invoice_type == 'gtgt':
            raise ValidationError(_('Vui lòng cung cấp mã số thuế của khách hàng để xuất hóa đơn GTGT.'))
        
        # TODO: Thực hiện kết nối API với nhà cung cấp HĐĐT
        # Đây là phần cần triển khai tùy theo nhà cung cấp dịch vụ hóa đơn
        
        # Cập nhật thông tin hóa đơn điện tử
        vals = {
            'e_invoice_status': 'signed',
            'e_invoice_number': self.invoice_number,
            'e_invoice_series': self.invoice_series,
            'e_invoice_date': self.invoice_date
        }
        
        record.write(vals)
        
        # Gửi email nếu được chọn
        if self.auto_send_email and record.partner_id.email:
            template = self.env.ref('vietnam_sale.mail_template_e_invoice')
            template.send_mail(record.id, force_send=True)
        
        # Thông báo thành công
        message = _('Đã ký và gửi hóa đơn điện tử số %s, ký hiệu: %s.') % (self.invoice_number, self.invoice_series)
        record.message_post(body=message, message_type='notification')
        
        return {'type': 'ir.actions.act_window_close'}