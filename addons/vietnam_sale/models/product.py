# -*- coding: utf-8 -*-

from odoo import models, fields, api


class VietnamProduct(models.Model):
    _inherit = 'product.template'
    
    vn_product_unit = fields.Char(string='Đơn vị tính', default='Cái')
    vn_product_code = fields.Char(string='Mã hàng hóa (HĐĐ)')
    
    # Giá bán lẻ/sỉ
    retail_price = fields.Float(string='Giá bán lẻ', default=0.0)
    wholesale_price = fields.Float(string='Giá bán sỉ', default=0.0)
    
    # Chiết khấu theo số lượng
    discount_tier1_qty = fields.Integer(string='Số lượng bậc 1', default=30, 
                                      help='Số lượng tối thiểu để được chiết khấu bậc 1 (10%)')
    discount_tier2_qty = fields.Integer(string='Số lượng bậc 2', default=50,
                                      help='Số lượng tối thiểu để được chiết khấu bậc 2 (15%)')
    discount_tier3_qty = fields.Integer(string='Số lượng bậc 3', default=100,
                                      help='Số lượng tối thiểu để được chiết khấu bậc 3 (deal trực tiếp)')
    
    discount_tier1_rate = fields.Float(string='Chiết khấu bậc 1 (%)', default=10.0)
    discount_tier2_rate = fields.Float(string='Chiết khấu bậc 2 (%)', default=15.0)
    
    # Phương thức tính giá bán sỉ tự động
    @api.onchange('list_price', 'discount_tier1_rate')
    def _onchange_compute_wholesale_price(self):
        for product in self:
            if not product.wholesale_price or product.wholesale_price == 0:
                # Nếu giá bán sỉ chưa được thiết lập, tính theo chiết khấu bậc 1
                product.wholesale_price = product.list_price * (1 - product.discount_tier1_rate / 100)
    
    # Tính giá theo số lượng
    def get_price_by_quantity(self, quantity):
        self.ensure_one()
        if quantity >= self.discount_tier3_qty:
            # Trả về giá đặc biệt hoặc giá bán sỉ làm cơ sở đàm phán
            return self.wholesale_price
        elif quantity >= self.discount_tier2_qty:
            # Áp dụng chiết khấu bậc 2
            return self.list_price * (1 - self.discount_tier2_rate / 100)
        elif quantity >= self.discount_tier1_qty:
            # Áp dụng chiết khấu bậc 1
            return self.list_price * (1 - self.discount_tier1_rate / 100)
        else:
            # Giá bán lẻ
            return self.list_price