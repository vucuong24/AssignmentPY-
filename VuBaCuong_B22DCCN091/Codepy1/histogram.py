import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Đọc dữ liệu từ file CSV
df = pd.read_csv('result.csv')

# Xác định các chỉ số cụ thể để vẽ histogram
stat_columns = ['Age', 'MP', '90s']

# 1. Vẽ histogram phân bố cho mỗi chỉ số trên toàn giải
def plot_histogram(data, columns, group_name):
    for col in columns:
        plt.figure(figsize=(10, 6))
        sns.histplot(data[col].dropna(), kde=True, bins=20, color='blue')
        plt.title(f'Phân bố {col} - {group_name}')
        plt.xlabel(col)
        plt.ylabel('Tần suất')
        plt.tight_layout()
        plt.show()

# Vẽ cho toàn giải đấu
plot_histogram(df, stat_columns, 'Toàn giải')

# 2. Vẽ histogram phân bố cho mỗi chỉ số cho từng đội
def plot_histograms_by_team(data, columns, team_col):
    for team, group in data.groupby(team_col):
        plot_histogram(group, columns, team)

# Vẽ cho từng đội
plot_histograms_by_team(df, stat_columns, 'Squad')