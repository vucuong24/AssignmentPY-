from sklearn.linear_model 
import LinearRegression
import numpy as np

# Dữ liệu mẫu: [Tuổi, Số bàn thắng, Số kiến tạo]
X = np.array([
    [23, 15, 10],
    [27, 25, 5],
    [21, 8, 7],
    [30, 5, 3]
])
# Giá trị chuyển nhượng (triệu Euro)
y = np.array([50, 70, 30, 15])

# Huấn luyện mô hình
model = LinearRegression()
model.fit(X, y)

# Dự đoán giá trị cầu thủ mới
new_player = np.array([[25, 20, 8]])
predicted_value = model.predict(new_player)
print(f"Giá trị dự đoán: {predicted_value[0]:.2f} triệu Euro")
