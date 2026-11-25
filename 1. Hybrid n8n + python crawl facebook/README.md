# Crawl bài tuyển dụng Facebook → CSV trên OneDrive → báo cáo Excel

Cập nhật 29/10/2026. Thay luồng cũ (scraper → Google Drive → n8n → Google Sheets) bằng luồng chạy hoàn toàn trên máy + OneDrive.

## Luồng
```
fb_scraper_no_login_v2.py  (Chrome cài sẵn, 5 group công khai, không đăng nhập Facebook)
   → fb_posts_*.json        (bản thô, nằm cạnh script)
   → fb_transform.py        (port của node n8n "Lọc trường1": tên công ty, địa chỉ, ngày đăng; loại trùng theo link)
   → fb_enrich.py           (tỉnh, ngành, vị trí, lương, kinh nghiệm, điểm lead)
   → fb_customers.py        (đối chiếu CRM, đọc 3. Reference\customers_index.csv)
   → 2. Output\fb_leads\fb_leads_YYYYMMDD_HHMM.csv
   → Excel: Power Query gộp thư mục (fb_leads_PowerQuery.pq) hoặc make_fb_report.py → 2. Output\FB_Leads_Report.xlsx
```
Mỗi lượt chạy tạo một file CSV mới; không bao giờ ghi đè file cũ.

## Cài đặt một lần
```
py -m pip install playwright pandas xlsxwriter openpyxl rapidfuzz
```
Python 3.14 và Google Chrome cài sẵn trên máy (scraper điều khiển Chrome này, không cần profile riêng, không cần đăng nhập Facebook).
Dự phòng: `py -m playwright install chromium` rồi đặt `BROWSER_CHANNEL = None` trong `fb_scraper_no_login_v2.py` để dùng Chromium của Playwright (đã cài ở ổ C trên máy này, nhưng chậm hơn nhiều).

## Chạy
Thư mục: `1. Set up\python`
| Việc | Lệnh |
|---|---|
| Chạy 1 lượt | `py fb_scraper_no_login_v2.py --once` |
| Chạy liên tục (mỗi 30 phút) | `py fb_scraper_no_login_v2.py` |
| Xuất CSV sang thư mục khác (test) | thêm `--out-dir D:\thu_muc_test` |
| Vẫn đẩy JSON lên Google Drive | thêm `--upload-drive` (cần credentials.json/token.json của Google) |
| Tạo báo cáo Excel | `py make_fb_report.py` |
| Làm mới danh sách CRM | `py build_customer_index.py` (đọc `02. Follow Client\10. All Sources.xlsx`, chỉ đọc) |

Mỗi lượt mất khoảng 5–10 phút với Chrome (group 5 chậm nhất). Mỗi group thử lại tối đa 3 lần; mỗi bài tối đa 90 giây, mỗi group tối đa 900 giây.

## Đặt lịch (Task Scheduler)
```
powershell -ExecutionPolicy Bypass -File .\setup_scheduler.ps1
```
Mặc định: mỗi ngày lúc 09:00, 12:00, 15:00, 18:00 (đổi bằng `-StartAt`, `-EndAt`, `-EveryHours`). Gỡ: thêm `-Unregister`. Chạy thử ngay: `Start-ScheduledTask -TaskName FB-Scraper-Leads`. Log: `logs\scheduler_last_run.txt` và `logs\scraper_YYYYMMDD.log`. Máy phải bật và đã đăng nhập Windows. **Đã đăng ký ngày 30/10/2026.**

## Các cột trong CSV
9 cột đầu giống `2. Output\Format output.xlsx`, rồi các cột bổ sung.
| Cột | Ý nghĩa |
|---|---|
| Tên công ty, Địa chỉ, Ngày đăng bài | Bóc từ nội dung bằng quy tắc của n8n cũ. Khoảng 1/3 bài không bóc được tên công ty |
| Group | Group Facebook nguồn |
| Tỉnh/Thành | 63 tỉnh (tên cũ, cùng danh sách hệ thống crawl CV); lấy từ địa chỉ rồi tiêu đề |
| Ngành | Nhóm lớn theo từ khóa ở tiêu đề; "Khác" nếu không rõ |
| Vị trí tuyển, Lương, Lương min/max (triệu), Kinh nghiệm | Bóc theo từ khóa, để trống nếu không thấy |
| Loại email | Cá nhân (gmail, yahoo…) hoặc Doanh nghiệp |
| Điểm lead, Ghi chú lead | Xem công thức dưới |
| Trạng thái CRM, ID CRM, Tên trong CRM | Xem mục CRM |

**Điểm lead (0–100)**: tên công ty +25; email doanh nghiệp +20 (cá nhân +8); SĐT +15; địa chỉ +10; tỉnh +10; ngành +8; vị trí +7; lương +5; nghi tuyển dụng hộ −20. Đây là độ đầy đủ thông tin, không phải xác suất chốt được khách.

## Đối chiếu CRM
- "Có trong CRM": tên công ty (bỏ dấu, bỏ "Công ty/TNHH/Cổ phần…") trùng khít một tên trong `10. All Sources.xlsx`.
- "Nghi trùng CRM": giống ≥ 92% nhưng không trùng khít, **cần người kiểm tra**.
- "Chưa có trong CRM": không tìm thấy. Trống: không có tên công ty, tên chỉ là địa danh, hoặc là câu bị bóc nhầm.
- Danh sách này **không cho biết công ty có đang là khách trả tiền hay không**. Muốn biết phải đối chiếu thêm với `05. Follow Client` (chưa làm).
- `3. Reference\customers_index.csv` là bản rút gọn tên công ty + ID CRM, không có thông tin cá nhân. Làm mới bằng `build_customer_index.py` mỗi khi `10. All Sources.xlsx` đổi.

## Giới hạn đã biết
- Dữ liệu có email/SĐT người đăng tin: giữ trong thư mục không chia sẻ rộng.
- Cào Facebook có thể vi phạm điều khoản của họ; chỉ dùng cho 5 group công khai và mức độ thấp.
- Code n8n cũ có bước đổi chữ in đậm Unicode không bao giờ chạy được; bản Python giữ nguyên hành vi (`BOLD_FIX = False` trong `fb_transform.py`).
- Đo 29/10/2026 ở group 5: Chrome ~3 phút, Chromium ~13 phút (chưa rõ nguyên nhân). Chrome tự cập nhật nên nếu một ngày script lỗi sau khi Chrome lên bản mới, thử `BROWSER_CHANNEL = None`.
- Workflow n8n trong `1. Set up\n8n` không còn cần thiết cho luồng mới. Google Sheets "Tự động lấy Mã số thuế" vẫn được hệ thống 4 dùng, không xóa.
- Tên 63 tỉnh là tên cũ trước sáp nhập 2025.
