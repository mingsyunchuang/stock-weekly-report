import requests
from bs4 import BeautifulSoup

def get_eps_last5_years(tw_code, name):
    """
    回傳近五年 年度EPS資料： [{'ticker','name','year','dividend_yield','eps'}, ...]
    """
    url = f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=XX&STOCK_ID={tw_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://goodinfo.tw/'
    }
    try:
        s = requests.Session()
        res = s.get(url, headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', class_='b1 p4_2 r10_0') or soup.find('table', class_='b1 p4_2 r0_10 row_mouse_over')
        if not table:
            print(f"[Goodinfo] 查無財報表格: {url}")
            return []
        ths = table.find_all('th')
        years = []
        eps_idx = -1
        for idx, th in enumerate(ths):
            if "年度" in th.text:
                for k in range(idx + 1, idx + 11):
                    try:
                        y = ths[k].text.strip()
                        if y.isdigit():
                            years.append(int(y))
                    except: break
            if "EPS" in th.text and eps_idx < 0:
                eps_idx = idx
        eps_row = None
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if tds and ("每股盈餘" in tds[0].text or "EPS" in tds[0].text):
                eps_row = [td.text.strip().replace(',', '').replace('--', '') for td in tds]
                break
        if not years or not eps_row:
            print(f"[Goodinfo] 無法解析EPS表 or 找不到EPS行:{url}")
            return []
        result = []
        for i, year in enumerate(years[:5]):
            try:
                val = eps_row[i + 1]
                eps = float(val)
                result.append({
                    'ticker': f"{tw_code}.TW",
                    'name': name,
                    'year': year,
                    'dividend_yield': '-',
                    'eps': eps
                })
            except: continue
        return result
    except Exception as e:
        print(f"[Goodinfo] 解析失敗 {tw_code}: {e}")
        return []

def get_gp_detail_html(tw_code):
    """
    僅抓取 Goodinfo 個股主資料區塊 (div#divDetail)
    """
    url = f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={tw_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://goodinfo.tw/'
    }
    try:
        s = requests.Session()
        res = s.get(url, headers=headers, timeout=15)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        main_block = soup.select_one("div#divDetail")
        if main_block:
            return str(main_block)
        return "<div>找不到 Goodinfo 資料區塊</div>"
    except Exception as e:
        print(f"[Goodinfo] 取得個股頁失敗: {e}")
        return "<div>無法載入 Goodinfo 個股頁</div>"
