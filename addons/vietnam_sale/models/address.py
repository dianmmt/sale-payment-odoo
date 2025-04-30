# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResWard(models.Model):
    _name = 'res.ward'
    _description = 'Phường/Xã'
    
    name = fields.Char(string='Tên phường/xã', required=True)
    code = fields.Char(string='Mã', required=True)
    district_id = fields.Many2one('res.district', string='Quận/Huyện', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)


class ResDistrict(models.Model):
    _name = 'res.district'
    _description = 'Quận/Huyện'
    
    name = fields.Char(string='Tên quận/huyện', required=True)
    code = fields.Char(string='Mã', required=True)
    province_id = fields.Many2one('res.province', string='Tỉnh/Thành phố', required=True, ondelete='cascade')
    ward_ids = fields.One2many('res.ward', 'district_id', string='Danh sách phường/xã')
    active = fields.Boolean(default=True)
    
    def name_get(self):
        result = []
        for district in self:
            name = district.name
            if district.province_id:
                name = "%s (%s)" % (name, district.province_id.name)
            result.append((district.id, name))
        return result


class ResProvince(models.Model):
    _name = 'res.province'
    _description = 'Tỉnh/Thành phố'
    
    name = fields.Char(string='Tên tỉnh/thành phố', required=True)
    code = fields.Char(string='Mã', required=True)
    country_id = fields.Many2one('res.country', string='Quốc gia', required=True, default=lambda self: self.env.ref('base.vn'))
    district_ids = fields.One2many('res.district', 'province_id', string='Danh sách quận/huyện')
    active = fields.Boolean(default=True)
    
    # Mở rộng để hỗ trợ tìm kiếm theo quận/huyện
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', ('name', operator, name), ('district_ids.name', operator, name)] + args
        return super(ResProvince, self).name_search(name=name, args=args, operator=operator, limit=limit)
    
    def name_get(self):
        result = []
        for province in self:
            name = province.name
            if province.country_id and province.country_id.code != 'VN':
                name = "%s (%s)" % (name, province.country_id.name)
            result.append((province.id, name))
        return result


class ResCountryState(models.Model):
    _inherit = 'res.country.state'
    
    # Mở rộng để hỗ trợ tìm kiếm theo tỉnh/thành phố
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            provinces = self.env['res.province'].search([('name', operator, name)])
            if provinces:
                states = self.env['res.country.state'].search([('country_id.code', '=', 'VN')])
                args = ['|', ('id', 'in', states.ids), ('name', operator, name)] + args
        return super(ResCountryState, self).name_search(name=name, args=args, operator=operator, limit=limit)


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'
    
    province_id = fields.Many2one('res.province', string='Tỉnh/Thành phố')
    district_id = fields.Many2one('res.district', string='Quận/Huyện')
    ward_id = fields.Many2one('res.ward', string='Phường/Xã')
    
    @api.onchange('province_id')
    def _onchange_province_id(self):
        if self.province_id:
            self.district_id = False
            self.ward_id = False
            # Cập nhật country và state tương ứng để đồng bộ
            if self.province_id.country_id:
                self.country_id = self.province_id.country_id
            
            # Tìm state tương ứng (nếu có)
            if self.province_id.country_id.code == 'VN':
                state = self.env['res.country.state'].search([
                    ('country_id', '=', self.province_id.country_id.id),
                    ('name', 'ilike', self.province_id.name)
                ], limit=1)
                if state:
                    self.state_id = state
            
            return {'domain': {'district_id': [('province_id', '=', self.province_id.id)]}}
        return {'domain': {'district_id': []}}
    
    @api.onchange('district_id')
    def _onchange_district_id(self):
        if self.district_id:
            self.ward_id = False
            # Đảm bảo province_id đồng bộ
            if self.district_id.province_id:
                self.province_id = self.district_id.province_id
            
            return {'domain': {'ward_id': [('district_id', '=', self.district_id.id)]}}
        return {'domain': {'ward_id': []}}
    
    # Phương thức tạo địa chỉ theo chuẩn Việt Nam
    def _get_vietnamese_address(self):
        self.ensure_one()
        address_parts = []
        if self.street:
            address_parts.append(self.street)
        if self.ward_id:
            address_parts.append(self.ward_id.name)
        if self.district_id:
            address_parts.append(self.district_id.name)
        if self.province_id:
            address_parts.append(self.province_id.name)
        if self.country_id and self.country_id.code != 'VN':
            address_parts.append(self.country_id.name)
        
        return ', '.join(address_parts)