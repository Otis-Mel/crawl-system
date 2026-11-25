# Quy trình tool crawl lead Facebook

Cập nhật: 11/11/2026. Mục đích: mỗi ngày lấy thông tin nhà tuyển dụng (tên công ty, email, SĐT) từ bài tuyển dụng trong các group Facebook, gom thành cụm theo nhà tuyển dụng, đánh dấu độ tin cậy, rồi đưa vào các quy trình bán hàng. Mục tiêu: từ 200 lead mới mỗi ngày.

Chi tiết bộ lọc từng bước xem `Bo_loc_lead.md`. File này mô tả luồng chung.

## 1. Tổng quan luồng

```
Task Scheduler (09:00, 12:00, 15:00)
        │
        ▼
run_fb_parallel.ps1 ──► 4 tiến trình fb_scraper_no_login_v2.py (50 group, chia 4 phần)
        │                     │ ghi CSV từng group + file tiến độ
        │                     ▼
        │            2. Output\fb_leads\fb_leads_<ngày>_<giờ>_*.csv   (cột "Loại dòng": Lead mới / Bổ sung)
        ▼
fb_cluster.py ──► 2. Output\fb_master\fb_master.csv   (kho cụm + trạng thái Verified / Cần check)
        │
        ▼
fb_report.py ──► thông báo ngắn sau mỗi lượt
                 + file Excel cả ngày ở lượt cuối (2. Output\bao_cao\BaoCao_FB_Crawl_<ngày>.xlsx)
        │
        ▼
Đưa lead đã verified vào Follow Client / quy trình Tool DN mới   (mục 6, phần đề xuất)
```

Thư mục code: `1. Set up\python\`. Dữ liệu: `2. Output\`. Danh mục tham chiếu: `3. Reference\`.

## 2. Lịch chạy

- Task `FB-Scraper-Leads`: 09:00, 12:00, 15:00 mỗi ngày. Chạy ẩn qua `powershell.exe -WindowStyle Hidden -File run_fb_parallel.ps1`.
- Mỗi lượt có **giờ dừng** = 5 phút trước lượt kế (lượt cuối 17:40). Quá giờ thì dừng gọn, quá thêm 3 phút thì bị tắt cưỡng bức. Không có tiến trình nào chạy sau 18:00.
- `MultipleInstances = IgnoreNew`: lượt mới không chạy chồng lên lượt đang chạy.
- Mã thoát 1 của task nghĩa là "lượt có vấn đề" (group lỗi, bị cắt giờ, không có lead), không phải sập.
- Task `FB-Scraper-DailyCheck` (17:45) đã **tắt** từ 05/11/2026 vì báo cáo cả ngày được gửi ngay khi lượt cuối xong.

## 3. Crawl (mỗi lượt)

1. `groups.json` có 50 group (danh sách ở `3. Reference\groups_dang_crawl.csv`). Mỗi lượt chia 4 phần, 4 tiến trình khởi động cách nhau 61 giây.
2. Mỗi group: mở Chrome headless không đăng nhập, lấy khoảng 10 bài hiển thị (Facebook giới hạn chế độ ẩn danh), lọc theo từ khóa tuyển dụng.
3. Mở từng bài để lấy nội dung đầy đủ, giữ bài có **email hoặc SĐT hợp lệ**. Bài không có cả hai bị bỏ.
4. Nghỉ ngẫu nhiên 5–15 giây giữa các group. Group lỗi hoặc thấy 0 bài được nghỉ 5 phút rồi thử lại một lần ở cuối lượt.
5. CSV ghi nối ngay sau mỗi group, nên lượt bị dừng giữa chừng vẫn giữ kết quả các group đã xong.
6. Mỗi phần ghi file tiến độ `logs\status_<lượt>_part_N.json`.

## 4. Đối chiếu với kho và gom cụm

**Mỗi dòng mới được gán "Loại dòng" khi ghi CSV** (`fb_transform.py` gọi `fb_cluster.classify_new`):

| Loại dòng | Ý nghĩa | Xử lý |
|---|---|---|
| Lead mới | Nhà tuyển dụng chưa có trong kho | Ghi |
| Bổ sung | Nhà tuyển dụng cũ, bài mới thêm email / SĐT / tên công ty | Ghi, để bổ sung vào cụm |
| Trùng | Không thêm thông tin gì | Bỏ |

Chỉ dedup tuyệt đối theo **link bài**. Bài đăng lại có thể bổ sung thông tin nên không bị bỏ.

**Gom cụm** (`fb_cluster.py`, chạy sau mỗi lượt, tính lại toàn bộ kho từ đầu):
- Nối theo: email, SĐT (bỏ qua nếu bài có hơn 3 SĐT, vì là tin tổng hợp), tên công ty đã chuẩn hóa, tên miền email doanh nghiệp, nội dung bài giống hệt.
- Mỗi cụm là một nhà tuyển dụng. Thông tin được bổ sung dần mỗi khi crawl trúng lại.

**Tên công ty:** tên thương hiệu (ví dụ NOVALAND) cũng được tính là tên công ty. Nếu tra được, dùng tên đăng ký (`fb_company_lookup.py`): website của tên miền email (hiệu quả nhất), rồi Bing, rồi DuckDuckGo. Cột "Độ tin tên công ty" ghi nguồn tên. Tên bị loại: chức danh, lời rao tuyển, thông tin liên hệ, địa danh, từ chung chung.

**Trạng thái xác thực:**

| Trạng thái | Điều kiện |
|---|---|
| Verified đủ 3/3 | Có tên công ty + email + SĐT |
| Verified 2/3 | Có tên công ty + (email hoặc SĐT) |
| Cần check | Còn lại. Cột "Cần bổ sung" ghi thiếu gì |

Kho: `2. Output\fb_master\fb_master.csv`.

## 5. Báo cáo và thông báo

- `fb_notify.py`: toast Windows + ghi `logs\notify_log.txt`. Telegram và webhook chưa bật (`notify_config.json` đang để trống).
- Thông báo gồm: bắt đầu lượt, xong từng phần, tổng kết lượt, và LỖI (phần hỏng, group lỗi, bị cắt giờ, không có lead).
- Sau mỗi lượt: thông báo ngắn (lead mới, bổ sung, group xong/lỗi, tổng cụm, số verified).
- Lượt cuối ngày: `fb_report.py --full` dựng Excel cả ngày (sheet Theo lượt, Chất lượng kho, Group lỗi, Nhà tuyển dụng mới) và thông báo kèm đường dẫn.

## 6. Đưa lead vào các quy trình bán hàng

**Chỉ lấy lead đã Verified** (2/3 hoặc 3/3, luôn có tên công ty). Đối chiếu với CRM trong `02. Follow Client\13. Update Converted.xlsx` (sheet `Report_Accounts_info_new_Nhi1`) theo MST và tên công ty. CRM không có email hay SĐT, nên chỉ khớp theo MST và tên.

| Kết quả đối chiếu | Đi đâu |
|---|---|
| **Khớp CRM** | Vào quy trình Follow Client (bước 5 trong `PROCESS_Follow_Client.md`): thêm vào `10. All Sources.xlsx`, Source = `facebook`, Crawl ID = Cụm ID, ID CRM |
| **Không khớp** (khách mới) | Quy trình giống Tool DN mới: có SĐT thì IT đổ CRM, có email thì MKT gửi email hàng loạt |
| **Nghi khớp** | Lọc lại (so tên, MST, địa chỉ), rồi chia vào hai nhóm trên |

Mức khớp:
- Khớp chắc = trùng MST (10 số đầu) hoặc tên đầy đủ, và tên không phải chỉ là thương hiệu.
- Nghi khớp = khớp tên lõi (bỏ "Công ty/TNHH/CP"), khớp mờ từ 90%, nhiều công ty CRM cùng tên hoặc cùng MST, hoặc chỉ có tên thương hiệu.
- Không khớp = chưa thấy trong CRM.

**Kết quả chạy thử** ngày 10/11/2026 (334 lead verified; file `2. Output\bao_cao\Map_Lead_FB_CRM_20261110.xlsx`): khớp chắc 16, nghi khớp 57, không khớp 261.

### Phần này chưa hoàn tất

- Lọc 57 cụm nghi khớp và chia kênh SĐT/email cho khách mới: chưa làm.
- Ghi vào `10. All Sources.xlsx`: chưa làm. Cần backup vào `_backup_<ngày>`, người dùng đồng ý, và kiểm tra Power Query của file 05 chịu được Cụm ID dạng chữ (ví dụ `Cbd40abca`, trong khi Crawl ID hiện toàn số).
- All Sources chỉ là bảng ánh xạ. Bước 6 của Follow Client (refresh 05 rồi 08) chỉ ra số liệu cho khách có job trong `Report_Job_Crawler`. Lead Facebook không có job ở đó nên ghi vào All Sources chưa làm số liệu theo team/AM thay đổi. Muốn thấy khách CRM đang đăng tuyển trên Facebook trong số liệu đó phải đưa bài Facebook vào luồng job trên ổ P (cần leader và người quản lý crawler quyết).
- Lead trùng CRM của Tool DN mới đang chờ leader trả lời (ngày 11/11/2026). Chưa xác nhận câu trả lời đó có áp dụng cho lead Facebook.

## 7. Vận hành và giới hạn

- **Facebook giới hạn:** chế độ không đăng nhập chỉ thấy khoảng 10 bài mỗi group. Đăng nhập không giúp lấy nhiều hơn (ghi chú đã thử). Tăng lead bằng cách thêm group.
- **Throttling:** có lượt bị Facebook giới hạn (ví dụ lượt 3 ngày 06/11: 13 group lỗi, cả ngày chỉ 146 lead mới). Nguyên nhân chưa xác định.
- **Chất lượng tên:** hơn 1.000 cụm "Cần check" chủ yếu thiếu tên công ty. Tra Bing/DuckDuckGo/SĐT kém hiệu quả; Google chặn công cụ tự động. Cách thử tiếp theo: Google Programmable Search API (cần `3. Reference\google_api.json` gồm `api_key` và `cx`; gói miễn phí 100 truy vấn/ngày).
- **Lần chạy bù:** log ngày 08/11 có lượt 3 bắt đầu lúc 17:54 với giờ dừng 17:40 (chạy bù khi máy bật lại). Chưa kiểm tra nguyên nhân và hậu quả.

## 8. Các file chính

| File | Vai trò |
|---|---|
| `run_fb_parallel.ps1` | Điều phối lượt: chia phần, chạy song song, giờ dừng, gọi gom cụm, báo cáo, thông báo |
| `fb_scraper_no_login_v2.py` | Crawl một phần các group, ghi CSV và file tiến độ |
| `fb_transform.py` | Bóc tách trường, ghi CSV, gán "Loại dòng" |
| `fb_cluster.py` | Đối chiếu kho, gom cụm, chấm trạng thái, ghi `fb_master.csv` |
| `fb_company_lookup.py`, `fb_mst_lookup.py` | Tra tên đăng ký và MST |
| `fb_report.py` | Báo cáo ngắn mỗi lượt, Excel cả ngày ở lượt cuối |
| `fb_notify.py` | Toast, log, Telegram, webhook |
| `groups.json` | 50 group đang crawl (bản sao lưu: `groups_5original.json`, `groups_25.json`) |
| `Bo_loc_lead.md` | Chi tiết từng bộ lọc và tùy chọn dòng lệnh |
| `PROCESS_Follow_Client.md` (ở `02. Follow Client\`) | Quy trình folder Follow Client |
