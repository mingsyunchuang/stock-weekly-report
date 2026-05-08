import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def capture_river_charts(ticker):
    """
    抓取 winvest.tw 的本益比河流圖與股價淨值比河流圖
    """
    # 處理股票代號 (移除 .TW 或 .TWO)
    stock_id = ticker.split('.')[0]
    url = f"https://winvest.tw/Stock/Symbol/Comment/{stock_id}"
    
    # 設定 Chrome Options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 無頭模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1200,1000")
    
    output_dir = os.path.join('output', 'charts')
    os.makedirs(output_dir, exist_ok=True)
    
    pe_img_path = os.path.join(output_dir, f"{stock_id}_pe.png")
    pb_img_path = os.path.join(output_dir, f"{stock_id}_pb.png")
    
    driver = None
    try:
        # 初始化 Driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"正在前往 {url} 截取河流圖...")
        driver.get(url)
        
        # 等待頁面加載及圖表出現
        wait = WebDriverWait(driver, 30)
        time.sleep(5) # 額外等待 Vue 渲染
        
        # 滾動到底部以觸發懶加載 (河流圖可能在下方)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # 截取全螢幕供偵錯
        debug_full_path = os.path.join(output_dir, f"{stock_id}_debug_full.png")
        driver.save_screenshot(debug_full_path)
        print(f"偵錯全螢幕截圖已儲存：{debug_full_path}")

        # 本益比河流圖
        try:
            # 嘗試多種定位方式：ID 或包含標題文字的元素
            selectors = [
                (By.ID, "peRatioChartDiv"),
                (By.ID, "StockPERiverChart"),
                (By.XPATH, "//div[contains(., '本益比河流圖') and contains(@class, 'chart')]"),
                (By.XPATH, "//h2[contains(text(), '本益比河流圖')]/following-sibling::div")
            ]
            pe_chart = None
            for by, val in selectors:
                try:
                    pe_chart = wait.until(EC.visibility_of_element_located((by, val)))
                    if pe_chart: break
                except: continue
            
            if pe_chart:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pe_chart)
                time.sleep(2) # 等待渲染完成
                pe_chart.screenshot(pe_img_path)
                print(f"已儲存：{pe_img_path}")
            else:
                print(f"找不到本益比河流圖元素 ({stock_id})")
                pe_img_path = None
        except Exception as e:
            print(f"無法截取本益比河流圖 ({stock_id}): {e}")
            pe_img_path = None

        # 股價淨值比河流圖
        try:
            selectors = [
                (By.ID, "pbRatioChartDiv"),
                (By.ID, "StockPBRiverChart"),
                (By.XPATH, "//div[contains(., '股價淨值比河流圖') and contains(@class, 'chart')]"),
                (By.XPATH, "//h2[contains(text(), '股價淨值比河流圖')]/following-sibling::div")
            ]
            pb_chart = None
            for by, val in selectors:
                try:
                    pb_chart = wait.until(EC.visibility_of_element_located((by, val)))
                    if pb_chart: break
                except: continue

            if pb_chart:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pb_chart)
                time.sleep(2) # 等待渲染完成
                pb_chart.screenshot(pb_img_path)
                print(f"已儲存：{pb_img_path}")
            else:
                print(f"找不到股價淨值比河流圖元素 ({stock_id})")
                pb_img_path = None
        except Exception as e:
            print(f"無法截取股價淨值比河流圖 ({stock_id}): {e}")
            pb_img_path = None
            
        return pe_img_path, pb_img_path
        
    except Exception as e:
        print(f"Winvest 抓取異常 ({stock_id}): {e}")
        return None, None
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # 測試
    pe, pb = capture_river_charts("2330")
    print(f"PE: {pe}, PB: {pb}")
