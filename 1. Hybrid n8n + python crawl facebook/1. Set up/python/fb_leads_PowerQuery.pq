// Power Query: gộp mọi file fb_leads_*.csv trong thư mục thành một bảng.
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor > dán đoạn này > Close & Load.
// Sau này chỉ cần Data > Refresh All. Đổi FolderPath nếu thư mục OneDrive đổi chỗ.
// (Đã chạy thử trong Excel 29/10/2026 với 479 dòng, 20 cột. Nếu báo lỗi kiểu dữ liệu, bỏ bước "Typed" để xem dữ liệu thô.)
let
    FolderPath = "D:\OneDrive - Kariera Group\handover - MinhCao\Crawl System\1. Hybrid n8n + python crawl facebook\2. Output\fb_leads",
    Source     = Folder.Files(FolderPath),
    CsvOnly    = Table.SelectRows(Source, each Text.StartsWith([Name], "fb_leads_") and [Extension] = ".csv"),
    Parsed     = Table.AddColumn(CsvOnly, "Data", each
                    Table.PromoteHeaders(
                        Csv.Document([Content], [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
                        [PromoteAllScalars = true])),
    Combined   = Table.Combine(Parsed[Data]),
    // Số dùng dấu chấm thập phân (en-US); ô rỗng -> null
    Typed      = Table.TransformColumnTypes(Combined, {
                    {"STT", Int64.Type}, {"Điểm lead", Int64.Type},
                    {"Lương min (triệu)", type number}, {"Lương max (triệu)", type number},
                    {"Thời gian crawl", type datetime}}, "en-US")
in
    Typed
