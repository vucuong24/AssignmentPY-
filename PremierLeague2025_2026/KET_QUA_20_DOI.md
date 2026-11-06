# Kết quả xử lý 20 HTML - 06/11/2026

Đầu vào: `data/sources`; kết quả mới: `data/processed/fbref` và `outputs/fbref`.

## Bài 1: thu thập và làm sạch

Đọc đủ 20 HTML gốc, đúng Premier League mùa 2025-2026. Sau ghép PlayerID và lọc tổng phút >90 có 473 cầu thủ, 486 stint cầu thủ-đội. Canonical URL chỉ để xác minh, không được tải. Giữ nguyên HTML và ghi SHA-256.

Mỗi đội có 5 bảng standard, keeper, shooting, playing_time, misc. Chỉ phân tích các chỉ số thực có: tuổi, số trận/đá chính/phút, bàn thắng, kiến tạo, phạt đền, thẻ phạt, cú sút, sút trúng đích, cứu thua và sạch lưới thủ môn. Cầu thủ chưa thi đấu có MP=0 và phút trống được xử lý là 0 phút; người đã thi đấu mà thiếu phút bị báo lỗi. Cộng stint trước khi lọc và không cộng các tỷ lệ.

## Bài 2: thống kê

Top bàn thắng: Erling Haaland 27, Igor Thiago 22, Antoine Semenyo 17. Top kiến tạo: Bruno Fernandes 21, Rayan Cherki 12, Jarrod Bowen 11. Các số này mô tả snapshot HTML đã lưu.

Manchester City dẫn đầu tổng bàn và kiến tạo của nhóm cầu thủ đủ điều kiện, lần lượt 74 và 57. Aston Villa có tuổi trung bình cao nhất: 27,28. Tottenham có tổng thẻ vàng cao nhất (101), Chelsea tổng thẻ đỏ cao nhất (8); giá trị cao không phải thành tích tốt. Burnley dẫn đầu tổng cứu thua thủ môn (137).

Đã xuất top/bottom 3 cho mọi chỉ số số, median/mean/std toàn giải và 20 đội, đội dẫn đầu gồm mọi đồng hạng, 63 histogram Age/MP/90s. Tổng theo đội chỉ bao gồm cầu thủ đủ điều kiện và không phải bảng thành tích chính thức CLB.

## Bài 3: K-means/PCA/radar

Đặc trưng có thể dùng: Age, Min, Gls_per90, Ast_per90. Điền thiếu bằng median, chuẩn hóa StandardScaler, K-means k=5 với random_state=42. Silhouette khoảng 0,2850; PCA 2D giữ khoảng 57,25% phương sai. Có biểu đồ elbow/silhouette k=2-10, không khẳng định k=5 tối ưu.

Quy mô 5 cụm: 116, 63, 122, 139, 33 cầu thủ. Cụm 0 có tuổi trung bình cao nhất; cụm 1 bàn/90 trung bình cao nhất; cụm 2 có tuổi trung bình thấp nhất; cụm 3 có phút trung bình cao nhất; cụm 4 kiến tạo/90 trung bình cao nhất. Mã cụm không phải thứ hạng hoặc vị trí cầu thủ.

Radar so sánh Erling Haaland và Igor Thiago trong nhóm 46 cầu thủ cùng vị trí. CSV giữ cả giá trị gốc, percentile và cỡ nhóm tham chiếu. Không so diện tích radar như điểm chất lượng tổng hợp.

## Bài 4: phí chuyển nhượng

Đọc JSON FootballTransfers gốc đã lưu: 365 giao dịch, giữ 312 đúng mùa/đội, ghép chính xác 113 giao dịch với FBref theo tên duy nhất và đội. Không dùng giá FPL hoặc market value làm phí. Free=0; chưa biết=thiếu.

Train 84, test 29 giao dịch; không có cầu thủ trùng giữa hai tập. Đầu vào mô hình gồm Age, Min, Gls, Ast, MP. So sánh median baseline, RidgeLog, RandomForestLog. Chọn RandomForestLog theo MAE GroupKFold trên train; test MAE=19,451 triệu EUR, RMSE=30,426 triệu EUR, R²=0,0469. Baseline median có MAE=24,310 triệu EUR.

Thành tích cả mùa có thể diễn ra sau giao dịch, vì vậy đây chỉ là mô hình hồi cứu. Chưa hoàn thành dự báo phí trước chuyển nhượng có kiểm định theo thời gian; cần thống kê mùa trước và mốc thời gian để làm phần đó đúng nghĩa. Sai số mô hình hiện còn lớn.

## Tái lập

```powershell
cd D:\AssignmentPY\PremierLeague2025_2026
python main.py all --offline
python -m pytest -q
```

Báo cáo đầy đủ: `outputs/fbref/reports/BAO_CAO.html`, `.md`, `.pdf`. Manifest chứa hash đầu vào, phiên bản thư viện và kết quả từng bước. Quy trình và báo cáo cũ đã chuyển sang thư mục lưu trữ ngoài dự án; xem README.md để biết nơi khôi phục.
