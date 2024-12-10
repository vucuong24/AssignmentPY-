import pandas as pd

# Đọc tệp CSV
df = pd.read_csv('result.csv')

# Lấy danh sách các cột chỉ số (loại trừ 'Name' và 'Squad')
attribute_cols = df.select_dtypes(include=['number']).columns.tolist()

# Tạo DataFrame rỗng để lưu kết quả
teams = ['all'] + df['Squad'].unique().tolist()
# results = pd.DataFrame(index=teams) # This creates an empty DataFrame causing the issue.

# Initialize results DataFrame with a single row for 'all' and columns for stats
results = pd.DataFrame(index=['all'], columns=[f'{col}_{stat}' for col in attribute_cols for stat in ['Median', 'Mean', 'Std']]) 


# Hàm tính toán thống kê cho một nhóm (toàn bộ giải đấu hoặc từng đội)
def calculate_stats(group, prefix):
    stats = {}
    for col in attribute_cols:
        stats[f'{col}_Median'] = group[col].median()
        stats[f'{col}_Mean'] = group[col].mean()
        stats[f'{col}_Std'] = group[col].std()
    # Return a Series with the correct index to match the results columns
    return pd.Series(stats, name=prefix, index=results.columns)  

# Tính toán cho toàn bộ giải đấu
results.loc['all'] = calculate_stats(df, 'all')

# Tính toán cho từng đội và thêm vào kết quả
team_stats = df.groupby('Squad').apply(lambda x: calculate_stats(x, x.name))

#Append the team stats to the results DataFrame
results = pd.concat([results, team_stats.loc[teams[1:]]]) 


# Lưu kết quả vào tệp CSV
results.to_csv('results2.csv')