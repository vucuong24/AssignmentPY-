import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Giả định rằng dữ liệu cầu thủ đã được thu thập và lưu vào DataFrame 'df'

# Lọc các cột chỉ số
features = df[['Age', 'MP', 'Starts', 'Min', '90s', 'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR', 'xG', 'npxG', 'xAG']]

# Xử lý các cột chứa dấu phẩy
for col in features.select_dtypes(include=['object']).columns:
    features[col] = features[col].str.replace(',', '').astype(float)

# Chuẩn hóa dữ liệu
scaler = StandardScaler()
scaled_features = scaler.fit_transform(features)

# Áp dụng K-means clustering
k = 5  # Số lượng cụm mong muốn
kmeans = KMeans(n_clusters=k, random_state=42)
clusters = kmeans.fit_predict(scaled_features)

# Thêm nhãn cụm vào DataFrame
df['Cluster'] = clusters

# Lưu DataFrame với thông tin cụm vào file CSV
df.to_csv('result_with_clusters.csv', index=False)
print("Đã lưu kết quả phân nhóm vào file result_with_clusters.csv")


