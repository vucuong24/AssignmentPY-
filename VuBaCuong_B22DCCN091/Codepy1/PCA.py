import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer

# 1. Đọc dữ liệu từ file CSV
df = pd.read_csv('result.csv')

# 2. Chọn các cột dữ liệu số để áp dụng PCA
numerical_cols = df.select_dtypes(include=['number']).columns
df_numerical = df[numerical_cols]

# 3. Xử lý missing values bằng SimpleImputer
imputer = SimpleImputer(strategy='mean') # Sử dụng giá trị trung bình để thay thế NaN
imputed_data = imputer.fit_transform(df_numerical) 
df_imputed = pd.DataFrame(imputed_data, columns=numerical_cols)

# 4. Chuẩn hóa dữ liệu
scaler = StandardScaler()
scaled_data = scaler.fit_transform(df_imputed)

# 5. Áp dụng PCA để giảm chiều dữ liệu xuống 2 chiều
pca = PCA(n_components=2)
principalComponents = pca.fit_transform(scaled_data)
principalDf = pd.DataFrame(data=principalComponents, columns=['PC1', 'PC2'])

# 6. Kết hợp dữ liệu PCA với cột 'Squad' để phân cụm
finalDf = pd.concat([principalDf, df[['Squad']]], axis=1)

# 7. Vẽ biểu đồ phân cụm
plt.figure(figsize=(10, 8))
sns.scatterplot(x="PC1", y="PC2", hue="Squad", data=finalDf, palette="viridis", s=100, alpha=0.7)
plt.title('Biểu đồ phân cụm PCA 2D')
plt.xlabel('Thành phần chính 1 (PC1)')
plt.ylabel('Thành phần chính 2 (PC2)')
plt.legend(title='Đội', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.show()

