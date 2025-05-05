from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    # Ghi đè phương thức tính thuế để cố định 10%
    @api.depends('product_uom_qty', 'price_unit', 'discount')
    def _compute_amount(self):
        """
        Ghi đè phương thức tính thuế để cố định 10%
        """
        super(SaleOrderLine, self)._compute_amount()
        for line in self:
            # Tính lại price_tax là 10% của price_subtotal
            line.price_tax = line.price_subtotal * 0.1