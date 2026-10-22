# Global Futures OI Intelligence

Hệ thống Django thu thập, lưu trữ và phân tích Open Interest/COT từ nguồn công khai CFTC. Giai đoạn đầu chỉ dùng API Socrata công khai của CFTC; không tự động thu thập CME hoặc nguồn bị hạn chế bản quyền.

## Chức năng hiện có

- Django 5.2 + cấu hình PostgreSQL 17 qua biến môi trường.
- Ba dataset CFTC: `6dca-aqww`, `72hh-3qpy`, `gpe5-46if`.
- Lưu ngày báo cáo, ngày công bố nếu API cung cấp, nguồn, payload gốc và trạng thái từng lần đồng bộ.
- Chống trùng bằng khóa duy nhất `(source, report_date, market_code)` và `update_or_create`.
- Lệnh quản trị `sync_cftc`, log lỗi, timeout và kiểm thử idempotency.
- Collector phân trang `$limit/$offset`, retry tối đa 3 lần, transaction và upsert vị thế theo nhóm nhà giao dịch.
- Phân tích pandas: OI Change % theo chuỗi lịch sử, Net Position, Net Position/Total OI và xếp hạng tăng/giảm.
- Dashboard tại `/` có lọc thị trường/nhóm tài sản và biểu đồ Plotly.

## Chạy local

```powershell
Copy-Item .env.example .env
# sửa POSTGRES_PASSWORD và các biến PostgreSQL trong .env
& .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
& .\\.venv\\Scripts\\python.exe manage.py makemigrations
& .\\.venv\\Scripts\\python.exe manage.py migrate
& .\\.venv\\Scripts\\python.exe manage.py test
& .\\.venv\\Scripts\\python.exe manage.py sync_cftc legacy --limit 100
# các dataset được hỗ trợ: legacy, disaggregated, financial hoặc all
& .\\.venv\\Scripts\\python.exe manage.py sync_cftc all --limit 5000
# nhập file CFTC TFF đã tải về; có thể truyền XLS và TXT cùng lúc
& .\\.venv\\Scripts\\python.exe manage.py import_cftc_file data\\cfc\\raw\\FinFutYY.xls data\\cfc\\raw\\FinFutYY.txt --dry-run
& .\\.venv\\Scripts\\python.exe manage.py import_cftc_file data\\cfc\\raw\\FinFutYY.xls data\\cfc\\raw\\FinFutYY.txt
# chạy dashboard phát triển
& .\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000
```

Để chạy test không cần PostgreSQL, đặt `USE_SQLITE=True` trong `.env`.

Collector dùng endpoint Socrata công khai chính thức `https://publicreporting.cftc.gov/resource/{dataset}.json` cho `6dca-aqww`, `72hh-3qpy`, `gpe5-46if`. Nguồn được lưu trong `DataSource` cùng endpoint, giấy phép/ghi công, ngày báo cáo, ngày công bố (nếu API cung cấp) và trạng thái từng `SyncRun`. Report có ngày tương lai hoặc ngày công bố tương lai bị từ chối; ngày công bố thiếu được giữ là `NULL` và được hiểu là ngày công bố chưa được API cung cấp, không tự bịa ngày.

## Lộ trình tiếp theo

Giai đoạn 2 sẽ thêm OI Change/Z-Score/Net Long-Short, cảnh báo và dashboard Bootstrap/Plotly. Giai đoạn 3 sẽ tích hợp Ollama bằng dữ liệu đã xác minh, scheduler Windows và hoàn thiện vận hành. Không có chức năng giao dịch tự động.
