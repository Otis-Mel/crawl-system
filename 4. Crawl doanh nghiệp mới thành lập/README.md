# Crawl doanh nghiệp mới thành lập (doanhnghiep.biz -> Excel)

Thay cho workflow n8n + Google Sheet cũ (vẫn giữ ở `1. Set up/` để tham khảo).

- Script: `crawl_dn_moi.py`
- Chạy: `run_crawl.bat` (log ghi vào `logs/`)
- Output: `2. Output/Doanh nghiep moi thanh lap.xlsx` (cùng 11 cột với `Format output.xlsx`)

## Cách dùng
- Chạy hằng ngày: `run_crawl.bat` — lấy trang mới nhất, dừng khi gặp trang toàn MST đã có.
- Quét lại toàn bộ (tối đa 300 trang, ~9.000 DN): `run_crawl.bat --full`. Có thể ngắt và chạy lại, MST đã có sẽ được bỏ qua.
- Chạy thử: `python crawl_dn_moi.py --max-pages 3`

## Lưu ý
- Đóng file Excel trước khi chạy (đang mở thì không ghi được).
- MST lưu dạng text để giữ số 0 đầu.
- Cột Ngành nghề luôn "Chua cap nhat": trang chi tiết của site không có dữ liệu này.
- Site giới hạn ~300 trang danh sách mới nhất, nên chạy ít nhất vài ngày một lần để không sót.
