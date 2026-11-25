# Danh sách bộ lọc lead Facebook

Cập nhật 30/10/2026. Mô tả đúng code hiện tại của `fb_scraper_no_login_v2.py`, `fb_transform.py`, `fb_enrich.py`. Lịch tự động (09:00, 12:00, 15:00, 18:00) chạy với **cấu hình mặc định** ghi ở cột "Mặc định".

## 1. Cấp group
| Bộ lọc | Cách xử lý | Mặc định |
|---|---|---|
| Group không truy cập được ("This content isn't available", "must log in") | Bỏ group, ghi log | Bật |
| Thấy 0 bài trên trang | Thử lại tối đa 3 lần, mỗi lần mở trình duyệt mới, chờ 60 giây giữa các lần | Bật |
| Quá 900 giây cho một group | Dừng group đó, thử lại | Bật |
| Tối đa 50 bài ứng viên mỗi group | Ngừng thu thập khi đủ | Bật |
| Số lần cuộn mỗi group | 5 lần (đổi bằng `--scrolls N`) | 5 |

## 2. Bước 1: lọc sơ bộ trên feed
| Bộ lọc | Cách xử lý | Mặc định |
|---|---|---|
| Bài phải có link bài viết (`/posts/`, `/permalink/`, `story_fbid`) | Không có link thì bỏ | Bật |
| Trùng link trong cùng lượt chạy | Bỏ | Bật |
| Bài rỗng | Bỏ | Bật |
| Bài phải chứa từ khóa tuyển dụng | Không có từ khóa thì bỏ | Bật |
| Độ dài bài (trước đây tối thiểu 20 và 30 ký tự) | **Đã bỏ 30/10/2026** | Tắt |

Từ khóa tuyển dụng (không phân biệt hoa thường): tuyển dụng, cần tuyển, đang tuyển, tuyển gấp, tuyển nhân viên, tuyển kế toán, tuyển kỹ sư, tuyển lập trình, tuyển sale(s), tuyển thực tập, tuyển cộng tác viên, tuyển ctv, cần người, cần gấp, job, hiring, we are hiring, recruiter, recruitment, ứng tuyển, nộp hồ sơ, liên hệ hr, và "tuyển" (từ khóa này làm gần như mọi bài có chữ "tuyển" đều qua).

## 3. Bước 2: lấy nội dung đầy đủ và lọc liên hệ
Mở trang bài viết để lấy nội dung đầy đủ (tối đa 90 giây mỗi bài; quá giờ thì dùng nội dung xem trước).

Thứ tự kiểm tra:
1. Bài đã lấy trước đó (cùng link) → bỏ.
2. Bài có **email** hoặc **SĐT hợp lệ** → giữ lại để đối chiếu với kho (bước 4). **Không còn bỏ bài chỉ vì email/SĐT đã gặp** (từ 03/11/2026): bài đăng lại có thể thêm thông tin cho nhà tuyển dụng đã có.
3. Không có cả hai:
   - Mặc định: **bỏ** (đây là bước loại nhiều nhất, khoảng 4 trên 5 bài).
   - Khi chạy với `--accept-no-contact`: nhận, lọc trùng theo link.

SĐT hợp lệ: 10 số, đầu số 02/03/05/07/08/09 (hoặc dạng +84/84), không dính vào số tiền như `1.000.000.000`. Trả về dạng `0xxxxxxxxx`.

## 4. Khi ghi CSV
| Bộ lọc | Cách xử lý |
|---|---|
| Trùng link bài viết với các dòng đã có | Bỏ (không bao giờ ghi đè file cũ) |
| Đối chiếu với kho (`fb_cluster.classify_new`) | Mỗi dòng được gán cột "Loại dòng": **Lead mới** (nhà tuyển dụng chưa có trong kho), **Bổ sung** (đã có nhưng bài thêm email / SĐT / tên công ty mà cụm chưa có) hoặc **Trùng** (không thêm gì → mới bỏ). Cụm = các dòng chung email, SĐT, tên công ty, tên miền email doanh nghiệp hoặc nội dung bài giống hệt |
| CSV ghi từng group | CSV được ghi nối ngay sau mỗi group, nên lượt bị dừng giữa chừng vẫn giữ kết quả các group đã xong |
| Tên công ty là từ khóa tuyển dụng bóc nhầm (CẦN, TUYỂN, CẦN TUYỂN, TUYỂN GẤP, TUYỂN DỤNG, GẤP, HOT, HOT JOB, VIỆC LÀM, NHÂN SỰ) | Để trống, sau đó thử lấy từ tên miền email hoặc quy tắc dự phòng |
| Tên công ty chỉ gồm từ mô tả loại hình (ví dụ "Sản xuất & Thương mại cần", "đang cần") | Để trống (thêm 31/10/2026) |
| Lead không có tên công ty nhưng có địa chỉ cụ thể (có số nhà và dấu phẩy) | Tự tra như cách làm tay: Bing "địa chỉ + mst công ty", mở tối đa 4 trang danh bạ doanh nghiệp, chỉ nhận công ty có địa chỉ đăng ký trùng số nhà + tên đường (`fb_mst_lookup.py`). Đúng 1 công ty: điền "Tên công ty" + "MST". Nhiều công ty cùng địa chỉ: không gán, chỉ ghi vào "Ghi chú tra MST". Không tìm thấy: để trống. Tắt bằng `--no-mst`. Kết quả nhớ trong `3. Reference\mst_cache.json` |
| Lead vẫn chưa có tên công ty sau bước tra | Cột "Link tra MST": link tìm kiếm Google để người xem tự kiểm (Google chặn máy chạy tự động nên không tra tự động bằng Google) |
| Ô bắt đầu bằng `=`, `+`, `-`, `@` | Thêm dấu nháy `'` ở đầu để Excel không hiểu là công thức |
| Ngày đăng không đọc được | Dùng ngày crawl |

## 5. Chấm điểm (không loại bài, chỉ để lọc và sắp xếp)
| Có thông tin | Điểm |
|---|---|
| Tên công ty | +25 |
| Email doanh nghiệp / email cá nhân | +20 / +8 |
| SĐT | +15 |
| Địa chỉ | +10 |
| Tỉnh/thành | +10 |
| Ngành (khác "Khác") | +8 |
| Vị trí tuyển | +7 |
| Lương | +5 |
| Nghi tuyển hộ hoặc công ty nhân sự | −20 |

Điểm nằm trong khoảng 0–100. Đây là độ đầy đủ thông tin, không phải xác suất chốt được khách. Cột "Ghi chú lead" ghi các điểm thiếu: "Thiếu tên công ty", "Email cá nhân", "Chỉ có SĐT", "Không có email/SĐT", "Nghi tuyển dụng hộ / công ty nhân sự".

## 6. Cột đánh dấu (không loại bài)
- **Bài cũ**: "Có" nếu ngày đăng cách ngày crawl quá 7 ngày.
- **Trạng thái CRM**: "Có trong CRM", "Nghi trùng CRM" (giống ≥ 92%), "Chưa có trong CRM", hoặc để trống (không có tên công ty, tên là địa danh hoặc là câu bị bóc nhầm).

## 7. Những thứ chưa lọc
- Bài cũ vẫn được nhận, chỉ đánh dấu.
- Người đăng cá nhân (không phải doanh nghiệp) vẫn được nhận.
- Không có ngưỡng điểm tối thiểu.
- Công ty nhân sự / headhunt chỉ bị trừ 20 điểm, không bị loại.

## 8. Bảng cụm và trạng thái xác thực (`fb_cluster.py` → `2. Output\fb_master\fb_master.csv`)
Sau mỗi lượt crawl, toàn bộ kho được gom thành cụm nhà tuyển dụng (mỗi dòng bảng = một cụm: tên công ty + email + SĐT), tính lại từ đầu nên thông tin được bổ sung dần.
| Trạng thái | Điều kiện |
|---|---|
| Verified đủ 3/3 | có tên công ty + email + SĐT |
| Verified 2/3 | có tên công ty + (email hoặc SĐT) |
| Cần check | còn lại; cột "Cần bổ sung" ghi thiếu gì |

- Tên thương hiệu (vd NOVALAND) tính là tên công ty. Có tên thương hiệu thì tra tên đăng ký bằng `fb_company_lookup.py`: website công ty (theo tên miền email), rồi Bing, rồi DuckDuckGo. Tra được thì dùng tên đăng ký + MST; không thì giữ tên thương hiệu.
- Cột "Độ tin tên công ty": Tên đăng ký (tra website/MST) / Có loại hình công ty (Công ty, TNHH, Tập đoàn...) / Khớp tên miền email / Khớp MST/CRM / Thương hiệu (chưa tra được, nên kiểm lại).
- Tên bị loại (không tính là tên công ty): chức danh, lời rao tuyển, thông tin liên hệ, địa danh, từ chung chung, câu viết thường toàn bộ.
- Bài có hơn 3 SĐT không dùng SĐT để nối cụm (tin tổng hợp/môi giới), ghi chú ở cột "Ghi chú".

## 9. Lịch và thông báo
- Task `FB-Scraper-Leads`: 09:00, 12:00, 15:00 mỗi ngày, gọi `run_fb_parallel.ps1` (4 tiến trình song song, chạy ẩn). Mỗi lượt có giờ dừng = 5 phút trước lượt kế (lượt cuối 17:40); quá giờ thì tự dừng gọn, quá thêm 3 phút thì bị tắt cưỡng bức, nên không có tiến trình nào chạy sau 18:00.
- Group lỗi/thấy 0 bài không thử lại dồn dập: để nguội 5 phút rồi thử lại một lần ở cuối lượt. Nghỉ ngẫu nhiên 5–15 giây giữa các group.
- Thông báo qua `fb_notify.py` (cấu hình trong `notify_config.json`): bắt đầu lượt, xong từng phần, tổng kết lượt, LỖI (phần hỏng, group lỗi, bị cắt giờ, không có lead). Sau mỗi lượt có thông báo tóm tắt ngắn (số lead mới, bổ sung, group xong/lỗi, kho). Chỉ lượt cuối ngày `fb_report.py` mới dựng báo cáo Excel đầy đủ cả ngày `2. Output\bao_cao\BaoCao_FB_Crawl_YYYYMMDD.xlsx` (sheet Theo lượt, Chất lượng kho, Group lỗi, Nhà tuyển dụng mới) và thông báo kèm đường dẫn. Báo cáo cả ngày được gửi ngay khi lượt cuối xong (thông báo kèm đường dẫn file Excel và tổng lead cả ngày). Task `FB-Scraper-DailyCheck` 17:45 đã TẮT từ 05/11/2026 vì trùng với thông báo này.

## 10. Tùy chọn dòng lệnh liên quan
| Tùy chọn | Tác dụng |
|---|---|
| `--once` | Chạy một lượt rồi dừng (Task Scheduler dùng tùy chọn này) |
| `--accept-no-contact` | Nhận cả bài không có email/SĐT |
| `--scrolls N` | Số lần cuộn mỗi group |
| `--groups FILE` | Dùng file group khác `groups.json` |
| `--out-dir DIR` | Ghi CSV vào thư mục khác (dùng khi thử) |
| `--deadline HH:MM` | Quá giờ này thì dừng gọn, không bắt đầu group/bài mới |
| `--status-file FILE` | Ghi tiến độ (JSON) sau mỗi group cho `run_fb_parallel.ps1` báo cáo |
| `--profile DIR` | Dùng profile Chrome đã đăng nhập Facebook (thử nghiệm, chưa cho kết quả tốt hơn) |

