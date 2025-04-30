# -*- coding: utf-8 -*-
{
    'name': 'Vietnam Sale',
    'version': '1.0',
    'summary': 'Module quản lý bán hàng phù hợp với đặc thù của doanh nghiệp Việt Nam',
    'description': """
        Module quản lý bán hàng Việt Nam
        ===============================
        - Quản lý địa chỉ theo chuẩn Việt Nam (Tỉnh/Thành phố, Quận/Huyện, Phường/Xã)
        - Hỗ trợ xuất hóa đơn điện tử theo quy định Việt Nam
        - Phân loại khách hàng lẻ và sỉ, chính sách chiết khấu theo số lượng
        - Thanh toán trả góp và theo dõi lịch thanh toán
        - Báo giá cho khách hàng sỉ
    """,
    'author': 'DiepAnh',
    'website': 'https://www.yourcompany.com',
    'category': 'Sales',
    'depends': ['sale_management', 'account', 'mail', 'base', 'sale', 'contacts', 'product'],  # Removed contacts
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/address_data.xml',
        'data/cron_data.xml',
        'data/mail_template_data.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/address_views.xml',
        'views/installment_views.xml',
        'views/menu_views.xml',
        'wizards/e_invoice_wizard_views.xml',
        'wizards/wholesale_quotation_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}