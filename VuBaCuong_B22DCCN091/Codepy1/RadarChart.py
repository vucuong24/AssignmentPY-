import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse

def create_radar_chart(df, player1, player2, attributes):
    # Kiểm tra nếu cầu thủ không tồn tại
    if player1 not in df['Name'].values or player2 not in df['Name'].values:
        print("Lỗi: Không tìm thấy một trong hai cầu thủ trong dữ liệu.")
        return

    # Lọc dữ liệu của các cầu thủ
    try:
        player1_data = df[df['Name'] == player1][attributes].values.flatten()
        player2_data = df[df['Name'] == player2][attributes].values.flatten()
    except KeyError:
        print("Lỗi: Một hoặc nhiều thuộc tính không hợp lệ.")
        return

    # Số lượng thuộc tính
    num_attributes = len(attributes)

    # Góc cho mỗi trục
    angles = np.linspace(0, 2 * np.pi, num_attributes, endpoint=False).tolist()

    # Đóng biểu đồ (kết nối điểm đầu và cuối)
    player1_data = np.concatenate((player1_data, [player1_data[0]]))
    player2_data = np.concatenate((player2_data, [player2_data[0]]))
    angles += angles[:1]

    # Tạo biểu đồ radar
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    # Vẽ biểu đồ cho mỗi cầu thủ
    ax.plot(angles, player1_data, 'o-', linewidth=2, label=player1)
    ax.fill(angles, player1_data, alpha=0.25)

    ax.plot(angles, player2_data, 'o-', linewidth=2, label=player2)
    ax.fill(angles, player2_data, alpha=0.25)

    # Cài đặt nhãn cho các thuộc tính
    ax.set_thetagrids(np.degrees(angles[:-1]), labels=attributes)

    # Tiêu đề và chú thích
    ax.set_title(f"So sánh giữa {player1} và {player2}")
    ax.legend(loc='upper right')

    # Hiển thị biểu đồ
    plt.show()

if __name__ == "__main__":
    try:
        # Phân tích các tham số dòng lệnh
        parser = argparse.ArgumentParser(description="Tạo biểu đồ radar so sánh hai cầu thủ.")
        parser.add_argument("--p1", required=True, help="Tên của cầu thủ thứ nhất")
        parser.add_argument("--p2", required=True, help="Tên của cầu thủ thứ hai")
        parser.add_argument("--Attribute", required=True, help="Danh sách các thuộc tính cần so sánh, ngăn cách bởi dấu phẩy")
        args = parser.parse_args()
        
        player1 = args.p1
        player2 = args.p2
        attributes = args.Attribute.split(',')
    
    except SystemExit:
        # Chế độ tương tác nếu thiếu tham số dòng lệnh
        print("Chạy ở chế độ tương tác. Sử dụng giá trị mặc định cho cầu thủ và thuộc tính.")
        player1 = "Erling Haaland"
        player2 = "Robert Lewandowski"
        attributes = ['Age', 'MP', 'Starts', 'Min']

    # Đọc dữ liệu từ file CSV
    df = pd.read_csv("result.csv")

    # Tạo biểu đồ radar
    create_radar_chart(df, player1, player2, attributes)
