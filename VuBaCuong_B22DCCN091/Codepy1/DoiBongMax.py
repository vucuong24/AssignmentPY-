import pandas as pd

# Đọc dữ liệu từ file CSV
df = pd.read_csv('result.csv')

# Hàm tìm đội có giá trị cao nhất cho mỗi chỉ số
def find_top_teams(data):
    for column in data.columns[5:]:  # Bắt đầu từ cột thứ 5 ('MP')
        if pd.api.types.is_numeric_dtype(data[column]):  # Kiểm tra nếu cột có kiểu dữ liệu số
            max_value = data[column].max()  # Tìm giá trị lớn nhất
            top_teams = data.loc[data[column] == max_value, 'Squad'].unique()  # Lọc đội bóng
            print(f"\u0110ội bóng có chỉ số {column} cao nhất: {top_teams}")
        else:
            print(f"Bỏ qua cột '{column}' (kiểu dữ liệu không phải số)")

# Gọi hàm để tìm đội
find_top_teams(df)
