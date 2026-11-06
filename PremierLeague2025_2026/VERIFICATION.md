# Kiểm chứng phiên bản tinh gọn

Ngày kiểm tra: 06/11/2026, múi giờ Asia/Ho_Chi_Minh.

## Kiểm tra chương trình

- python -m pytest -q: 25 kiểm thử đạt, tập trung vào quy trình hiện tại, bao gồm kiểm thử từ điển báo cáo chỉ chứa các cột có dữ liệu.
- Chạy đầy đủ main.py all với kết nối socket bị chặn để kiểm tra không phụ thuộc mạng.
- Bộ kiểm thử giả lập dùng thư mục tạm; các kiểm thử snapshot dùng 20 HTML người dùng cung cấp.
- Các kiểm thử FPL/Transfermarkt cũ đã chuyển ra ngoài cùng quy trình không còn dùng.

## Kiểm tra dữ liệu và mô hình

- 20 HTML có hash khớp metadata, 473 PlayerID duy nhất với tổng phút >90, 486 stint.
- Bảo toàn Min/Gls/Ast/MP/Starts khi cộng các stint; thống kê CSV được đối chiếu với tính trực tiếp.
- 63 histogram, K-means 5 cụm, silhouette khoảng 0,28496; PCA 2D giữ khoảng 57,2509% phương sai.
- Radar Haaland/Igor Thiago: giá trị gốc và percentile được lưu cùng cỡ nhóm tham chiếu.
- 365 giao dịch gốc, 312 đúng phạm vi, ghép 113; train 84/test 29 và không trùng cầu thủ.
- Chọn mô hình theo CV train; tính lại MAE/RMSE từ từng dự đoán test.
- RandomForestLog: MAE 19,451 triệu EUR, RMSE 30,426 triệu EUR, R² 0,0469. Mô hình chỉ phân tích hồi cứu.

## Kiểm tra báo cáo

Báo cáo PDF 19 trang đã được render và xem toàn bộ để kiểm tra font, bảng, hình và phân trang. Báo cáo HTML tự chứa hình và có phụ lục 63 histogram. run_manifest.json ghi phiên bản thư viện, hash HTML và kết quả mỗi bước.

Sau chỉnh nội dung báo cáo, đã xuất lại HTML/Markdown/PDF và xem các trang thay đổi: từ điển, đầu vào mô hình, nguồn gốc và bảng đã trích xuất theo đội. Kiểm tra văn bản cả ba định dạng: không còn chỉ số kỳ vọng, chuyền tịnh tiến hoặc phòng ngự chưa thu được. PDF giữ 19 trang, không có ký tự thay thế U+FFFD.

Đã đối chiếu 446 tệp trong data/sources với bản ZIP trước tinh gọn: tất cả có SHA-256 giữ nguyên. Đã chuyển 319 tệp thừa (khoảng 32,29 MB) khỏi thư mục dự án vào kho lưu trữ. Số mô-đun trong epl giảm từ 13 xuống 8; các lệnh phân tích hiện tại vẫn hoạt động.

## Khôi phục

Toàn bộ dự án trước tinh gọn đã được nén tại D:\AssignmentPY\_archive\PremierLeague2025_2026_before_cleanup_20261106.zip và kiểm tra CRC không lỗi. Các mục chuyển khỏi thư mục làm việc nằm trong D:\AssignmentPY\_archive\cleanup_removed_20261106.
