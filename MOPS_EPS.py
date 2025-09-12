import requests
from bs4 import BeautifulSoup

def year_to_minguo(year):
    return str(int(year) - 1911)

def fetch_eps_mops(stock_id, max_count=5, verify_ssl=False):
    """
    自動往前找有EPS的年度（不會問未結帳的當年度）
    """
    from datetime import datetime
    now = datetime.now()
    current_year = now.year - 1  # 避免未結年度
    eps_result = []
    count = 0
    year = current_year
    while count < max_count and year >= 2015:
        y_minguo = year_to_minguo(year)
        url = "https://mops.twse.com.tw/mops/web/ajax_t163sb04"
        params = {
            "encodeURIComponent":1, "step":1, "firstin":1, "off":1,
            "queryName":"co_id", "inpuType":"co_id",
            "TYPEK": "sii", "year": y_minguo, "co_id": stock_id
        }
        try:
            res = requests.post(url, data=params, timeout=10, verify=verify_ssl)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            table = soup.find("table", class_="hasBorder")
            if not table:
                print(f"[MOPS] {stock_id}/{year} 查無表格")
                year -= 1
                continue
            trs = table.find_all("tr")
            col_idx = -1
            eps_val = "-"
            name = "-"
            # 標題行
            for idx, th in enumerate(trs[0].find_all(["th","td"])):
                if "每股盈餘" in th.text:
                    col_idx = idx
            for tr in trs[1:]:
                tds = tr.find_all("td")
                if len(tds)>2 and col_idx>=0:
                    name = tds[1].text.strip().replace("\xa0","").replace(" ","")
                    eps_val = tds[col_idx].text.strip().replace(",", "").replace("--","")
                    break
            if col_idx==-1 or eps_val in ['','-','--'] or not name:
                print(f"[MOPS] {stock_id}/{year} 無EPS")
                year -= 1
                continue
            eps_result.append({
                "ticker":f"{stock_id}.TW",
                "name": name,
                "year": int(year),
                "eps": float(eps_val)
            })
            count += 1
        except Exception as e:
            print(f"[MOPS] 解析失敗 {stock_id}/{year}: {e}")
        year -= 1
    return eps_result

# 測試例
if __name__ == "__main__":
    eps = fetch_eps_mops("2330", max_count=5, verify_ssl=False)
    print(eps)
