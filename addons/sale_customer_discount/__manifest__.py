{
    'name': "Sale Customer Discount",
    'summary': "Áp dụng giảm giá dựa trên lịch sử mua hàng của khách hàng",
    'description': """
        Module này mở rộng chức năng của module Sale của Odoo để:
        - Kiểm tra lịch sử mua hàng của khách hàng khi tạo báo giá mới
        - Hiển thị số lượng đơn hàng đã hoàn thành của khách hàng
        - Cho phép người dùng chọn áp dụng giảm giá cho khách hàng thân thiết
        - Áp dụng mức giảm giá phù hợp dựa trên số lượt mua hàng
    """,
    'author': "Odoo Vietnam",
    'version': '1.0',
    'depends': ['sale'],
    'data': [
        'views/sale_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
} 