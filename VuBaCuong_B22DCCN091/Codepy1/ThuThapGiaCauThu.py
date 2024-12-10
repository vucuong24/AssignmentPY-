import requests
from bs4 import BeautifulSoup as bs
import pandas as pd

# URL gốc
base_url = "https://www.footballtransfers.com"

# Hàm để lấy dữ liệu từ một trang
def scrape_transfers(page):
    url = f"{base_url}/transfers?page={page}"
    response = requests.get(url)
    soup = bs(response.content, 'html.parser')

    # Tìm các khối chứa thông tin cầu thủ
    players = []
    for item in soup.find_all('div', class_='transfer-item'):
        name = item.find('span', class_='player-name').text.strip()
        club_from = item.find('div', class_='club-from').text.strip()
        club_to = item.find('div', class_='club-to').text.strip()
        price = item.find('div', class_='price').text.strip()
        players.append([name, club_from, club_to, price])
    return players

# Thu thập dữ liệu từ nhiều trang
all_players = []
for page in range(1, 5):  
    all_players.extend(scrape_transfers(page))

# Lưu vào DataFrame và xuất CSV
columns = ['Name', 'Club From', 'Club To', 'Price']
df = pd.DataFrame(all_players, columns=columns)
df.to_csv('transfer_values.csv', index=False)
print("Dữ liệu đã được lưu vào 'transfer_values.csv'")
