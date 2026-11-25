# Quy trình Crawl doanh nghiệp mới thành lập

Cập nhật: 11/11/2026. Mục đích: lấy danh sách doanh nghiệp mới từ doanhnghiep.biz, đối chiếu với CRM, rồi chia lead cho IT (đổ vào CRM để sales gọi), MKT (gửi email hàng loạt) và Follow Client (lead đã có trong CRM).

## 1. Các file trong folder

| File / thư mục | Vai trò |
|---|---|
| `crawl_dn_moi.py` | Script crawl: doanhnghiep.biz -> Excel |
| `run_crawl.bat` | Chạy script bằng một click, ghi log vào `logs\` |
| `2. Output\Doanh nghiep moi thanh lap.xlsx` | Kho lead đã crawl, tích lũy (11 cột, khóa là MST) |
| `2. Output\Format output.xlsx` | File mẫu cũ của bản n8n (33.551 dòng, 3 tháng 4–6/2026), không dùng nữa |
| `3. Chuyen giao\<ngày>\` | Các file giao cho IT, MKT và danh sách lead trùng CRM |
| `1. Set up\1. Workflow n8n\` | Workflow n8n + Google Sheet cũ, giữ để tham khảo |
| `README.md` | Hướng dẫn chạy nhanh |

File tham chiếu ngoài folder: `02. Follow Client\13. Update Converted.xlsx`, sheet `Report_Accounts_info_new_Nhi1` (danh sách khách trong CRM, dùng cột `MaSoThue` để đối chiếu).

## 2. Luồng dữ liệu

```
doanhnghiep.biz
      │  crawl_dn_moi.py (lịch 12h T2–T6)
      ▼
2. Output\Doanh nghiep moi thanh lap.xlsx   (~14.300 lead)
      │  đối chiếu MST với CRM (13. Update Converted.xlsx)
      ├── có SĐT (hoặc SĐT + email) ─────► IT: đổ vào CRM cho sales gọi
      ├── có email (hoặc SĐT + email) ───► MKT: gửi email hàng loạt
      ├── không có SĐT lẫn email ────────► bỏ
      └── trùng CRM (đã có MST) ─────────► Follow Client (xem mục 5)
```

## 3. Bước 1: Crawl

Chạy tự động bằng lịch `crawl-dn-moi-thanh-lap` (Claude Scheduled Tasks) lúc **12h các ngày thứ 2 đến thứ 6**. Chạy tay bằng `run_crawl.bat`.

1. Đọc danh sách các trang của site (30 doanh nghiệp mỗi trang, tối đa 300 trang).
2. Lấy MST của từng doanh nghiệp, bỏ qua MST đã có trong file.
3. Với MST mới, mở trang chi tiết và lấy tên, người đại diện, địa chỉ, ngày cấp, SĐT, email (email được giải mã từ Cloudflare).
4. Gặp trang mà toàn bộ MST đã có thì dừng sớm.
5. Ghi vào file Excel. MST lưu dạng text để giữ số 0 đầu, cột trùng MST không tồn tại.

Tùy chọn:
- `--full`: quét hết các trang, không dừng sớm (dùng khi nghi sót, mất khoảng 15–20 phút).
- `--max-pages N`: giới hạn số trang (dùng để chạy thử).
- `--workers N`: số luồng lấy chi tiết (mặc định 4).

Cột của file lead: STT, MST, Tên công ty, Người đại diện, Địa chỉ, Ngành nghề, Ngày cấp, SĐT, Email, Ngày crawl, Link masothue.

## 4. Bước 2: Phân loại và chuyển giao

Đối chiếu MST của lead với cột `MaSoThue` trong CRM (so 10 chữ số đầu, bỏ hậu tố chi nhánh như -001). Sau đó chia:

| Nhóm | Điều kiện | Đi đâu | Số lượng (11/11/2026) |
|---|---|---|---|
| IT | Không trùng CRM, có SĐT (kể cả có cả email) | Đổ vào CRM cho sales gọi | 13.900 |
| MKT | Không trùng CRM, có email (kể cả có cả SĐT) | Gửi email hàng loạt | 5.152 |
| Bỏ | Không trùng CRM, không có SĐT lẫn email | Không xuất | 181 |
| Trùng CRM | MST đã có trong CRM | Follow Client | 165 |

- Lead có cả SĐT lẫn email (khoảng 5.065) nằm ở cả file IT và file MKT. Leader đã đồng ý cách chia này.
- File IT và MKT xuất theo form `new_accout_Hung_2025.xlsx` (22 cột). Các cột đã điền: STT, Company Name, Location (tỉnh/thành), Email DN, Người đại diện, Địa chỉ, SĐT - Hotline, Final MST. Các cột còn lại để trống: mã CRM (id, id_contact, email_address_id, email_address_id_DN, code_c), Website, SĐT - Người đại diện, Ngành, Quy mô, thông tin nhân sự.
- Tên file giao: `1. IT - Lead co SDT (form Hung).xlsx`, `2. MKT - Lead co email (form Hung).xlsx`, `3. Lead trung CRM (cho hoi leader).xlsx` (file 3 gồm ID_CRM, sales phụ trách, trạng thái CRM).

## 5. Bước 3: Lead trùng CRM vào Follow Client

Leader yêu cầu "map vào process Follow Client". Cụ thể chưa được xác nhận, dưới đây là đề xuất sau khi đối chiếu (chưa thực hiện).

Process Follow Client (xem `02. Follow Client\PROCESS_Follow_Client.md`) khóa theo (Source + Crawl ID) -> ID CRM trong `10. All Sources.xlsx`, không dùng MST. Trong 165 lead trùng:

| Tình trạng | Số lead | Việc cần làm |
|---|---|---|
| Đã có trong `10. All Sources` | 119 | Không cần làm gì |
| Trong đó đã có job trong Job Raw của file 08 | 76 (1.291 job) | Không cần làm gì |
| Chưa có trong All Sources | 46 | Vào Step 4 và 5 |

Với 46 lead chưa có mapping:
1. **Step 4:** dùng MST và tên để tìm công ty trên job crawl (TopCV, VietnamWorks, vieclam24h), lấy Crawl ID. Cần bật VPN vì `Report_Job_Crawler` nằm ở ổ P.
2. **Step 5:** thêm dòng (Source, Crawl ID, Company Name, ID CRM) vào bảng `Sources_Raw` của `10. All Sources.xlsx`.
3. **Step 6:** refresh file 05 rồi file 08 trong lần chạy tới.

Công ty chưa đăng tin trên trang nào thì chưa có Crawl ID để thêm.

## 6. Cách vận hành

- Chạy hằng ngày: lịch 12h tự chạy, hoặc `run_crawl.bat`.
- Quét lại toàn bộ: `run_crawl.bat --full`.
- Đóng file Excel trước khi chạy (đang mở thì không ghi được).
- Lịch chạy khi app Claude đang mở. Nếu app đóng lúc 12h, lịch chạy bù khi mở lại.
- Site chỉ cho xem tối đa 300 trang mới nhất (khoảng 9.000 doanh nghiệp), nên không nên để quá vài ngày không chạy.

## 7. Vấn đề đã biết

- **Cột Ngành nghề luôn là "Chua cap nhat":** trang chi tiết của site không có dữ liệu ngành.
- **Site cập nhật theo đợt dồn:** có ngày 0 doanh nghiệp mới là bình thường (ví dụ site đứng ở ngày 04/11 trong nhiều ngày, rồi đăng dồn 2.288 doanh nghiệp một lần).
- **Danh sách có cả công ty cũ:** trang chủ site liệt kê doanh nghiệp vừa được cập nhật, nên có lead có ngày cấp từ 1998.
- **Tên công ty có thể có ký tự lỗi "�"** vì nguồn đã lỗi sẵn.
- **Đối chiếu CRM dùng file ngày 21/10:** khách mới vào CRM sau ngày đó chưa được tính, nên một số lead trong file IT có thể đã trùng.
- **Dữ liệu cá nhân:** SĐT và email thu thập từ nguồn công khai, cần xem lại quy định nội bộ về dữ liệu trước khi dùng để gọi hoặc gửi email chào bán.
- **Script tạo file chuyển giao (đối chiếu CRM, chia IT/MKT, xuất theo form) hiện chạy tay**, chưa nằm trong folder và chưa tự chạy theo lịch.

## 8. Việc đang chờ

- Leader xác nhận cách đưa 46 lead trùng CRM chưa có mapping vào Follow Client.
- Đưa script tạo file chuyển giao vào folder và nối vào lịch 12h (nếu muốn tự động).
- Bản CRM mới hơn để đối chiếu chính xác.
