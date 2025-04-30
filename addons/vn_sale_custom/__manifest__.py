{
    'name': 'Vietnam Sale Process',
    'version': '16.0.1.0.0',
    'summary': 'Quy trình bán hàng cho doanh nghiệp Việt Nam',
    'description': """
        Module này mở rộng quy trình bán hàng của Odoo để phù hợp với các doanh nghiệp tại Việt Nam.
        Tính năng chính:
        - Hỗ trợ thanh toán trả góp với các kỳ hạn khác nhau có thể cấu hình
        - Tính toán lãi suất tự động với khả năng tùy chỉnh theo tháng
        - Tính thuế GTGT 10% tự động
        - Hiển thị thông tin trả góp trực tiếp trong trang đơn hàng
        - Hệ thống cảnh báo thanh toán trước hạn 1 tuần cho cả khách hàng và nhân viên nội bộ
    """,
    'category': 'Sales',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'AGPL-3',
    'depends': ['sale', 'account', 'mail'],
    'data': [
    # Security phải đứng sau các views
        'views/sale_order_views.xml',
        'views/installment_plan_views.xml',
        'views/installment_term_views.xml',
        'views/payment_reminder_views.xml',
        'security/ir.model.access.csv',  # Đặt security file sau
        'data/payment_reminder_cron.xml',
        'data/mail_template_data.xml',
        'data/installment_term_data.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}