import requests
from bs4 import BeautifulSoup as bs
import pandas as pd

# Danh sách các URL
urls = [
    'https://fbref.com/en/squads/b8fd03ef/2023-2024/Manchester-City-Stats',
    'https://fbref.com/en/squads/18bb7c10/2023-2024/Arsenal-Stats',
    'https://fbref.com/en/squads/8602292d/2023-2024/Aston-Villa-Stats',
    'https://fbref.com/en/squads/4ba7cbea/2023-2024/Bournemouth-Stats',
    'https://fbref.com/en/squads/cd051869/2023-2024/Brentford-Stats',      'https://fbref.com/en/squads/d07537b9/2023-2024/Brighton-and-Hove-Albion-Stats',
    'https://fbref.com/en/squads/943e8050/2023-2024/Burnley-Stats',
    'https://fbref.com/en/squads/cff3d9bb/2023-2024/Chelsea-Stats',
    'https://fbref.com/en/squads/47c64c55/2023-2024/Crystal-Palace-Stats',
    'https://fbref.com/en/squads/d3fd31cc/2023-2024/Everton-Stats',
    'https://fbref.com/en/squads/fd962109/2023-2024/Fulham-Stats',      'https://fbref.com/en/squads/822bd0ba/2023-2024/Liverpool-Stats',
    'https://fbref.com/en/squads/e297cd13/2023-2024/Luton-Town-Stats',
    'https://fbref.com/en/squads/19538871/2023-2024/Manchester-United-Stats',
    'https://fbref.com/en/squads/b2b47a98/2023-2024/Newcastle-United-Stats',
    'https://fbref.com/en/squads/e4a775cb/2023-2024/Nottingham-Forest-Stats',
    'https://fbref.com/en/squads/1df6b87e/2023-2024/Sheffield-United-Stats',
    'https://fbref.com/en/squads/361ca564/2023-2024/Tottenham-Hotspur-Stats',
    'https://fbref.com/en/squads/7c21e445/2023-2024/West-Ham-United-Stats',
    'https://fbref.com/en/squads/8cec06e1/2023-2024/Wolverhampton-Wanderers-Stats'
]

# Hàm lấy dữ liệu từ một bảng
def extract_table_data(soup, table_id, player_name, start_col, end_col, col_count):
    table = soup.find('table', {'id': table_id})
    if not table:
        return ['N/A'] * col_count
    for row in table.find_all('tr'):
        name_tag = row.find('th', attrs={'data-stat': 'player'})
        if name_tag and name_tag.text.strip() == player_name:
            columns = row.find_all('td')[start_col:end_col]
            return [(col.text.strip() if col.text.strip() else 'N/A') for col in columns]
    return ['N/A'] * col_count

# Hàm xử lý dữ liệu từ một URL
def process_url(url):
    response = requests.get(url)
    soup = bs(response.content, 'html.parser')

    squad_tag = soup.find('div', {'id': 'info'}).find('span') if soup.find('div', {'id': 'info'}) else None
    squad = ''.join(squad_tag.text.strip().split()[1:-1]) if squad_tag else 'N/A'

    main_table = soup.find('table', {'id': 'stats_standard_9'})
    if not main_table:
        return []

    players_data = []
    for row in main_table.find_all('tr'):
        name_tag = row.find('th', attrs={'data-stat': 'player'})
        position_tag = row.find('td', attrs={'data-stat': 'position'})
        nation_tag = row.find('span', style="white-space: nowrap")
        minutes_tag = row.find('td', attrs={'data-stat': 'minutes'})

        if not (name_tag and nation_tag and minutes_tag):
            continue

        name = name_tag.text.strip()
        position = position_tag.text.strip() if position_tag else 'N/A'
        nation = nation_tag.text.strip().split()[-1]
        minutes = minutes_tag.text.strip().replace(',', '')
        if not (minutes.isdigit() and int(minutes) > 90):
            continue

        base_data = [name, squad, nation, position]
        base_data += [cell.text.strip() for cell in row.find_all('td')[2:-1]]

        # Thêm dữ liệu từ các bảng khác
        base_data += extract_table_data(soup, 'stats_keeper_9', name, 7, -1, 15)
        base_data += extract_table_data(soup, 'stats_shooting_9', name, 4, -1, 15)
        base_data += extract_table_data(soup, 'stats_passing_9', name, 4, -1, 23)
        base_data += extract_table_data(soup, 'stats_passing_types_9', name, 5, -1, 14)
        base_data += extract_table_data(soup, 'stats_gca_9', name, 4, -1, 16)
        base_data += extract_table_data(soup, 'stats_defense_9', name, 4, -1, 16)
        base_data += extract_table_data(soup, 'stats_possession_9', name, 4, -1, 22)
        base_data += extract_table_data(soup, 'stats_playing_time_9', name, 3, -1, 22)
        base_data += extract_table_data(soup, 'stats_misc_9', name, 4, -1, 16)

        players_data.append(base_data)
    return players_data

# Lấy dữ liệu từ tất cả các URL
all_players = []
for url in urls:
    all_players.extend(process_url(url))

# Sắp xếp và chuyển đổi thành DataFrame
all_players.sort(key=lambda x: (x[0], int(x[4]) if x[4].isdigit() else 0))
columns = ['Name', 'Squad', 'Nation', 'Position' , 'Age', 'MP', 'Starts', 'Min', '90s', 'Gls', 'Ast', 'G+A', 'G-PK', 'PK', 'PKatt', 'CrdY', 'CrdR', 'xG', 'npxG', 'xAG', 'npxG+xAG', 'PrgC', 'PrgP', 'PrgR', 'Gls', 'Ast', 'G+A', 'G-PK', 'G+A-PK', 'xG', 'xAG', 'xG+xAG', 'npxG', 'npxG+xAG', 'GA', 'GA90', 'SoTA', 'Saves', 'Save%', 'W', 'D', 'L', 'CS', 'CS%', 'PKatt', 'PKA', 'PKsv', 'PKm', 'Save%',
                                        'Gls','Sh','SoT', 'Sot%', 'Sh/90', 'SoT/90', 'G/Sh', 'G/SoT', 'Dist', 'FK', 'PK', 'PKatt', 'xG', 'npxG', 'npxG/Sh', 'G-xG', 'np:G-xG','Cmp', 'Att', 'Cmp%','TotDist','PrgDist', 'Cmp','Att','Cmp%','Cmp','Att','Cmp%','Cmp','Att','Cmp%','Ast','xAG','xA','A-xAG','KP','1/3.','PPA','CrsPA','PrgP',
                                        'Live','Dead','FK','TB','Sw','Crs','TI','CK','In','Out','Str','Cmp','Off','Blocks','SCA','SCA90','PassLive','PassDead','TO','Sh','Fld','Def','GCA','GCA90','PassLive','PassDead','TO','Sh','Fld','Def',
                                        'Tkl','TklW','Def3rd','Mid3rd','Att3rd','Tkl','Att','Tkl%','Lost','Blocks','Sh','Pass','Int','Tkl+Int','Clr','Err',
                                        'Touches','DefPen','Def3rd','Mid3rd','Att3rd','AttPen','Live','Att','Succ','Succ%','Tkld','Tkld%','Carries','TotDist','PrgDist','PrgC','1/3.','CPA','Mis','Dis','Rec','PrgR',
                                        'MP','Min','Mn/MP','Min%','90s','Starts','Mn/Start','Compl','Subs','Mn/Sub','unSub','PPM','onG','onGA','+/-','+/-90','On-Off','onxG','onxGA','xG+/-','xG+/-90','On-Off',
                                        'CrdY','CrdR','2CrdY','Fls','Fld','Off','Crs','Int','TklW','PKwon','PKcon','OG','Recov','Won','Lost','Won%']

df = pd.DataFrame(all_players, columns=columns)

# Xuất kết quả ra file CSV
df.to_csv('result.csv', index=False)
print(df)
