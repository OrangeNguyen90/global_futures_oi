# Hướng dẫn cho agent và cộng tác viên

- Mục tiêu là nghiên cứu dữ liệu Futures; tuyệt đối không thêm chức năng đặt lệnh hoặc kết nối CME khi chưa có giấy phép.
- Không commit `.env`, mật khẩu, token hoặc dữ liệu nhạy cảm.
- Mọi nguồn dữ liệu mới phải ghi rõ giấy phép, endpoint, ngày báo cáo, ngày công bố và trạng thái đồng bộ.
- Thay đổi schema phải có migration. Thay đổi parser CFTC phải có test dữ liệu mẫu.
- Chạy `python manage.py test` trước khi bàn giao; ưu tiên interpreter `.venv` của dự án.
- Báo cáo AI chỉ được dùng dữ liệu đã lưu và xác minh trong database, không bịa số liệu.

