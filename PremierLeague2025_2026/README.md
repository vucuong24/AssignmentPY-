# Premier League 2025-2026

Phân tích 20 HTML FBref đã lưu và bản JSON FootballTransfers. Chương trình luôn đọc tệp cục bộ, không cần truy cập website.

## Chạy dự án

    cd D:\AssignmentPY\PremierLeague2025_2026
    python -m pip install -r requirements.txt
    python main.py all
    python -m pytest -q

Có thể dùng run.ps1 thay cho lệnh all. Tùy chọn --offline được giữ để tương thích với lệnh cũ; mọi lệnh luôn chạy cục bộ.

## Đầu vào và đầu ra

- data/sources/: 20 HTML gốc cùng các thư mục tài nguyên do trình duyệt lưu; giữ nguyên để đối chiếu.
- data/raw/: JSON giao dịch FootballTransfers và metadata nguồn/hash.
- data/processed/fbref/: result.csv, player_team_stints.csv, table_rows.csv, dữ liệu mô hình và data_quality.json.
- outputs/fbref/tables/: bảng thống kê, cụm, radar, chuyển nhượng và đánh giá mô hình.
- outputs/fbref/figures/: 63 histogram và các hình phân tích.
- outputs/fbref/models/: mô hình K-means/PCA và mô hình phí hồi cứu.
- outputs/fbref/reports/: báo cáo HTML/Markdown/PDF và run_manifest.json.

HTML báo cáo tự chứa hình và có phụ lục 63 histogram. PDF trình bày các hình chính. Xem KET_QUA_20_DOI.md để đọc kết quả từng bài và VERIFICATION.md để xem kiểm chứng.

## Các lệnh riêng

    python main.py prepare
    python main.py stats
    python main.py cluster --k 5
    python main.py radar --p1 "Erling Haaland" --p2 "Igor Thiago"
    python main.py transfers
    python main.py valuation
    python main.py report

prepare mặc định đọc data/sources. Đọc nơi khác bằng --html-dir "D:\ThuMucHTML". Phải đủ 20 đội; --allow-partial chỉ dùng kiểm tra tập nhỏ. fetch là tên tương thích của prepare. Tệp ThuThapBongDa.py ở thư mục AssignmentPY gọi cùng bước prepare.

Radar hỗ trợ --attributes "Gls_per90,Ast_per90,Min,MP"; thêm --all-positions nếu so sánh khác vị trí.

## Tổ chức mã nguồn

- main.py: lệnh điều phối.
- epl/common.py: đường dẫn, lưu tệp, hash và chuẩn hóa tên.
- epl/fbref_scraper.py: xác minh HTML, trích bảng, ghép PlayerID và lọc phút.
- epl/analysis.py: hàm thống kê và hình dùng chung.
- epl/transfers.py: xử lý phí và lọc giao dịch.
- epl/fbref_pipeline.py: bốn phần phân tích và tạo báo cáo.
- epl/report.py, epl/pdf_report.py: định dạng bảng và xuất PDF.
- tests/: kiểm thử bộ đọc, quy tắc dữ liệu và snapshot thật.

## Phạm vi phân tích

Sau lọc tổng phút >90 có 473 cầu thủ và 486 lượt cầu thủ-đội. Các stint được cộng trước khi lọc; không cộng tỷ lệ giữa các đội. Thống kê theo đội chỉ tính đóng góp của nhóm cầu thủ đủ điều kiện.

Chỉ dùng các chỉ số đã thu được. K-means dùng Age, Min, Gls_per90, Ast_per90; mô hình phí dùng Age, Min, Gls, Ast, MP. Từ điển trong báo cáo được tạo theo các cột thực có dữ liệu trong CSV.

Mô hình phí dùng thành tích và giao dịch cùng mùa nên chỉ phân tích hồi cứu. Muốn dự báo trước giao dịch cần thêm dữ liệu mùa trước và kiểm định theo thời gian.

## Phần đã lược bỏ

Đã bỏ quy trình FPL/Transfermarkt cũ, lệnh --source/--refresh/import-fbref/predict, dữ liệu và kết quả cũ, tài liệu trùng, ảnh kiểm tra tạm. Đã bỏ requests và lxml khỏi danh sách phụ thuộc vì quy trình hiện tại không sử dụng.

Phần chuyển ra khỏi dự án có thể khôi phục tại D:\AssignmentPY\_archive\cleanup_removed_20261106.
Bản ZIP nguyên trạng trước chỉnh sửa: D:\AssignmentPY\_archive\PremierLeague2025_2026_before_cleanup_20261106.zip.
