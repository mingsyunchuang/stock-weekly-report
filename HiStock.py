import requests
from bs4 import BeautifulSoup

def getHtmlData_eps(url):
    '''
    只回傳含有"歷年每股盈餘"表格的表頭與內容值，每次適用 histock 每股盈餘頁面
    '''
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.encoding = 'utf-8'
        root = BeautifulSoup(res.text, "html.parser")
        tables = root.find_all("table")
        for tbl in tables:
            ths = tbl.find_all("th")
            if ths and "歷年每股盈餘" in ths[0].get_text():
                # 第一列是 row label，餘欄是年度：['歷年每股盈餘', '2024', '2023', ...]
                h = [th.get_text(strip=True) for th in ths]
                tds = tbl.find_all("td")
                d = [td.get_text(strip=True) for td in tds]
                return h, d
        print("[HiStock] 找不到含「歷年每股盈餘」的table")
        return [], []
    except Exception as e:
        print(f"[HiStock] getHtmlData_eps error: {e}")
        return [], []

def get_eps_last5_years(tw_code, name):
    '''
    只回傳歷年每股盈餘annual合計資料（近五年，欄位依序為最新至最舊）
    '''
    url = f"https://histock.tw/stock/financial.aspx?no={tw_code}&st=2"
    h, d = getHtmlData_eps(url)
    if not h or not d or len(h) < 2 or len(d) < 1:
        print(f"[HiStock] 無法解析 EPS 年度表: {url}")
        return []
    # h = ['歷年每股盈餘', '2024', '2023', ...] (最新在左)
    # d = [EPS2024, EPS2023, ...] (最新在左)
    result = []
    for year, eps in zip(h[1:6], d[0:5]):
        try:
            result.append({
                'ticker': f"{tw_code}.TW",
                'name': name,
                'year': int(year),
                'dividend_yield': '-',
                'eps': float(eps.replace(",", ""))
            })
        except Exception:
            continue
    return result

# # 測試(開啟以下行直接可測)
# if __name__ == "__main__":
#     data = get_eps_last5_years("2330", "台積電")
#     print(data)
