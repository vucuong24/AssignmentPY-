# Premier League 2025-2026

Phân tích 20 HTML FBref đã lưu và bản JSON FootballTransfers. Chương trình luôn đọc tệp cục bộ, không cần truy cập website.

## Chạy từng bước trong VS Code

Mở terminal PowerShell. Từ `D:\AssignmentPY`, vào thư mục dự án.

```powershell
cd .\PremierLeague2025_2026
```

Nếu thư mục dự án chưa có `.venv`, tạo môi trường và cài thư viện một lần.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chạy từng dòng theo thứ tự và đợi mỗi bước hoàn tất trước khi chạy bước sau.

```powershell
.\.venv\Scripts\python.exe 01_thu_thap_du_lieu.py
.\.venv\Scripts\python.exe 02_thong_ke_histogram.py
.\.venv\Scripts\python.exe 03_bieu_do_ban_thang.py
.\.venv\Scripts\python.exe 04_kmeans_elbow_silhouette.py
.\.venv\Scripts\python.exe 05_bieu_do_pca.py
.\.venv\Scripts\python.exe 06_ban_do_nhiet_tam_cum.py
.\.venv\Scripts\python.exe 07_bieu_do_radar.py
.\.venv\Scripts\python.exe 08_ghep_chuyen_nhuong.py
.\.venv\Scripts\python.exe 09_bieu_do_phi_chuyen_nhuong.py
```

| Bước | Công việc và kết quả chính |
| --- | --- |
| 01 | Đọc 20 HTML đã lưu trong `data/sources/`. Xuất mỗi đội một CSV trong `data/processed/fbref/cau_thu_theo_doi/`, cùng các bảng tổng hợp và dữ liệu đã làm sạch trong `data/processed/fbref/`. |
| 02 | Đọc CSV từ bước 01, xuất bảng thống kê và 63 histogram về tuổi, số trận và số trận 90 phút quy đổi. |
| 03 | Đọc `team_totals.csv` từ bước 02 và vẽ `team_goals.png`. |
| 04 | Chạy K-means với 5 cụm, lưu bảng và mô hình, rồi vẽ Elbow và Silhouette trong `kmeans_diagnostics.png`. |
| 05 | Dùng tọa độ đã lưu ở bước 04 để vẽ `pca_clusters.png`. |
| 06 | Dùng tâm cụm đã lưu ở bước 04 để vẽ `cluster_profiles.png`. |
| 07 | Vẽ `radar.png` cho hai cầu thủ cùng vị trí được chọn tự động và xuất bảng phân vị. |
| 08 | Ghép JSON FootballTransfers đã lưu với dữ liệu FBref và xuất `transfers_with_fbref.csv`. |
| 09 | Đọc kết quả bước 08, đánh giá mô hình hồi cứu và vẽ `valuation_predictions.png`. |

## Đầu vào và đầu ra

- data/sources/: 20 tệp HTML gốc dùng để trích xuất và đối chiếu dữ liệu.
- data/raw/: JSON giao dịch FootballTransfers và metadata nguồn/hash.
- data/processed/fbref/: mở `tong_hop_bang_thu_thap.csv` trong Excel để xem các loại bảng FBref thu được, số đội có dữ liệu, số dòng trước lọc và chỉ số tiêu biểu. `table_rows.csv` giữ các dòng chi tiết, còn `result.csv` và `player_team_stints.csv` chứa dữ liệu đã làm sạch.
- data/processed/fbref/cau_thu_theo_doi/: 20 file CSV, mỗi file là danh sách cầu thủ của một đội trước khi lọc tổng số phút. Tiêu đề cột dùng tiếng Việt và các dòng được sắp theo số phút thi đấu giảm dần.
- outputs/fbref/tables/: bảng thống kê, cụm, radar, chuyển nhượng và đánh giá mô hình.
- outputs/fbref/figures/: 63 histogram và các hình phân tích.
- outputs/fbref/models/: mô hình K-means/PCA và mô hình phí hồi cứu.

## Tùy chọn phân tích

Dùng tùy chọn trực tiếp trên file của bước tương ứng để đổi thư mục HTML, số cụm hoặc cặp cầu thủ.

```powershell
.\.venv\Scripts\python.exe 01_thu_thap_du_lieu.py --html-dir "D:\ThuMucHTML"
.\.venv\Scripts\python.exe 04_kmeans_elbow_silhouette.py --k 5
.\.venv\Scripts\python.exe 07_bieu_do_radar.py --p1 "Erling Haaland" --p2 "Igor Thiago"
```

Bước 01 yêu cầu đủ 20 đội. Tùy chọn `--allow-partial` dùng để kiểm tra tập nhỏ. Sau khi đổi số cụm ở bước 04, chạy lại bước 05 và 06 để cập nhật hình. Radar hỗ trợ `--attributes "Gls_per90,Ast_per90,Min,MP"` và `--all-positions` để so sánh khác vị trí.

## Xem code khi demo

Mỗi file chứa phần xử lý của bước đó. Khi trình bày, mở file theo bảng trên và tìm hàm tương ứng.

| Bước | Hàm để trình bày |
| --- | --- |
| 01 | `collect_fbref` đọc và xuất dữ liệu, `parse_squad` đọc bảng của từng đội, `make_totals` cộng số liệu và lọc theo số phút. |
| 02 | `statistics` tính các bảng, `histogram` vẽ phân phối. |
| 03 | `team_goals` đọc bảng bàn thắng theo đội và vẽ biểu đồ thanh. |
| 04 | `clustering` chuẩn hóa, huấn luyện K-means, tính PCA và vẽ Elbow cùng Silhouette. |
| 05 | `pca_clusters` đọc tọa độ PCA và vẽ các điểm theo cụm. |
| 06 | `cluster_profiles` đọc tâm cụm và vẽ bản đồ nhiệt. |
| 07 | `radar` chọn cặp cầu thủ, gọi `percentile_scores` và vẽ biểu đồ radar. |
| 08 | `prepare_confirmed` lọc giao dịch và chuẩn hóa phí, `transfers` ghép hồ sơ với FBref. |
| 09 | `valuation` chia tập, huấn luyện, kiểm định và vẽ phí thực tế so với phí ước lượng. |

Các bước sau dùng chung đường dẫn, hàm đọc và ghi dữ liệu, kiểm tra mã băm và cấu hình biểu đồ từ bước 01.

## Phạm vi phân tích

Sau lọc tổng phút >90 có 473 cầu thủ và 486 lượt cầu thủ-đội. Các stint được cộng trước khi lọc; không cộng tỷ lệ giữa các đội. Thống kê theo đội chỉ tính đóng góp của nhóm cầu thủ đủ điều kiện.

Chỉ dùng các chỉ số đã thu được. K-means dùng Age, Min, Gls_per90, Ast_per90. Mô hình phí dùng Age, Min, Gls, Ast và MP.

Mô hình phí dùng thành tích và giao dịch cùng mùa nên chỉ phân tích hồi cứu. Muốn dự báo trước giao dịch cần thêm dữ liệu mùa trước và kiểm định theo thời gian.
