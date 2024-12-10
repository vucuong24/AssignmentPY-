import pandas as pd

# Đọc dữ liệu từ file CSV (giả sử file được lưu ở bước trước)
df = pd.read_csv('result.csv')

# Định nghĩa hàm để in top 3 cầu thủ có điểm cao nhất và thấp nhất cho mỗi chỉ số
def print_top_and_bottom_players(df, columns):
    for col in columns:
        # Chuyển đổi cột sang kiểu số, xử lý các giá trị không phải số
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Bỏ qua cột nếu không có dữ liệu số
        if df[col].isnull().all():
            continue

        # Lọc các hàng có giá trị hợp lệ (không phải NaN)
        valid_data = df.dropna(subset=[col])

        # Tìm top 3 cầu thủ có điểm cao nhất
        top_3 = valid_data.nlargest(3, col)[['Name', 'Squad', col]]
        
        # Tìm top 3 cầu thủ có điểm thấp nhất
        bottom_3 = valid_data.nsmallest(3, col)[['Name', 'Squad', col]]

        print(f"\nChỉ số: {col}")
        print("Top 3 cầu thủ có điểm cao nhất:")
        print(top_3)

        print("Top 3 cầu thủ có điểm thấp nhất:")
        print(bottom_3)

# Lựa chọn các cột có chỉ số cần so sánh
columns_to_compare = ['Gls', 'Ast', 'Min', 'xG', 'xAG', 'PrgP']

# Gọi hàm với DataFrame và danh sách các chỉ số
print_top_and_bottom_players(df, columns_to_compare)

