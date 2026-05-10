import yfinance as yf
import pandas as pd
import ta
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import os
import smtplib
import requests
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import make_msgid
from datetime import datetime, timedelta
from config import stock_targets
from Goodinfo import get_eps_last5_years, get_gp_detail_html
from winvest import capture_river_charts

# 備註：yfinance 現在內部使用 curl_cffi 處理 session，不建議手動傳入 requests session

# 設定字體以支援中文顯示
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

ticker_to_name = {t.upper(): name for t, name in stock_targets}

def download_and_calc_indicators(ticker, name):
    print(f"正在抓取 {name}({ticker}) ...")
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y") # 修改點：使用 1y 代替 max 以減少數據量與請求負擔
    if hist.empty:
        print(f"{ticker} 無法取得資料")
        return

    
    # 計算技術指標
    hist['MA20'] = hist['Close'].rolling(window=20).mean()
    bb = ta.volatility.BollingerBands(close=hist['Close'], window=20, window_dev=2)
    hist['BBL'] = bb.bollinger_lband()
    hist['BBM'] = bb.bollinger_mavg()
    hist['BBU'] = bb.bollinger_hband()
    
    macd = ta.trend.MACD(close=hist['Close'])
    hist['MACD'] = macd.macd()
    hist['MACD_signal'] = macd.macd_signal()
    hist['MACD_diff'] = macd.macd_diff()
    
    stoch = ta.momentum.StochasticOscillator(
        high=hist['High'], low=hist['Low'], close=hist['Close'], window=9, smooth_window=3)
    hist['KD_K'] = stoch.stoch()
    hist['KD_D'] = stoch.stoch_signal()
    
    hist['RSI'] = ta.momentum.RSIIndicator(close=hist['Close'], window=14).rsi()
    
    os.makedirs('output', exist_ok=True)
    hist.to_csv(f'output/{ticker.upper()}_indicators.csv')

# def plot_k_line_with_indicators(csv_path, stock_name):
# 修改點：增加接收 ticker 參數
def plot_k_line_with_indicators(csv_path, ticker, stock_name):
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    
    # 【修正 1】解決 Mixed Timezones 錯誤並去除時區資訊以利繪圖
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors='coerce', utc=True).tz_localize(None)
    else:
        df.index = df.index.tz_localize(None)

    df = df[df.index.notnull()]
    num_days = 60
    df_recent = df.tail(num_days)
    
    macd_diff = df_recent.get('MACD_diff', pd.Series(0, index=df_recent.index))
    macd_colors = np.where(macd_diff >= 0, 'red', 'green')
    
    addplots = []
    # Panel 0: 主圖區域
    if 'MA20' in df_recent.columns:
        addplots.append(mpf.make_addplot(df_recent['MA20'], color='blue', panel=0, width=1.0))
    if set(['BBL', 'BBM', 'BBU']).issubset(df_recent.columns):
        addplots.append(mpf.make_addplot(df_recent['BBL'], color='green', width=0.8))
        addplots.append(mpf.make_addplot(df_recent['BBM'], color='magenta', width=0.8))
        addplots.append(mpf.make_addplot(df_recent['BBU'], color='red', width=0.8))
    
    # Panel 1: MACD
    if set(['MACD', 'MACD_signal', 'MACD_diff']).issubset(df_recent.columns):
        addplots.append(mpf.make_addplot(df_recent['MACD'], color='purple', panel=1, width=1, ylabel='MACD'))
        addplots.append(mpf.make_addplot(df_recent['MACD_signal'], color='orange', panel=1, width=1))
        addplots.append(mpf.make_addplot(macd_diff, type='bar', color=macd_colors, panel=1, width=0.7, alpha=0.7))
    
    # Panel 2: KD
    if set(['KD_K', 'KD_D']).issubset(df_recent.columns):
        addplots.append(mpf.make_addplot(df_recent['KD_K'], color='dodgerblue', panel=2, width=1, ylabel='KD'))
        addplots.append(mpf.make_addplot(df_recent['KD_D'], color='gold', panel=2, width=1))
        kd_x = df_recent.index
        addplots.append(mpf.make_addplot(np.full(len(kd_x), 80), color='red', panel=2, secondary_y=False, width=1))
        addplots.append(mpf.make_addplot(np.full(len(kd_x), 20), color='green', panel=2, secondary_y=False, width=1))
    
    # Panel 3: RSI
    if 'RSI' in df_recent.columns:
        addplots.append(mpf.make_addplot(df_recent['RSI'], color='firebrick', panel=3, width=1, ylabel='RSI'))
        rsi_x = df_recent.index
        addplots.append(mpf.make_addplot(np.full(len(rsi_x), 70), color='red', panel=3, secondary_y=False, width=1))
        addplots.append(mpf.make_addplot(np.full(len(rsi_x), 30), color='green', panel=3, secondary_y=False, width=1))

    os.makedirs('output/charts', exist_ok=True)
    img_path = os.path.join('output', 'charts', os.path.basename(csv_path).replace('_indicators.csv', '.png'))
    
    mc = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='black')
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc)
   
#    fig, axes = mpf.plot(
#        df_recent, type='candle', style=s, ylabel='價格',
#        addplot=addplots,
#        title=f"{stock_name} 3-Month Analysis",
#        volume=False,
#        panel_ratios=(3, 1, 1, 1),
#        figratio=(16, 10), figscale=1.0,
#        returnfig=True)
    # 修改點：組合你想要的標題格式
    full_title = f"{ticker} {stock_name} (3-Month Analysis)"

    fig, axes = mpf.plot(
        df_recent, type='candle', style=s, ylabel='價格',
        addplot=addplots,
        title=full_title,  # 修改點：套用組合好的標題
        volume=False,
        panel_ratios=(3, 1, 1, 1),
        figratio=(16, 10), figscale=1.0,
        returnfig=True)

    try:
        # 【修正 2】使用指定的 axes 索引來繪製 scatter 標記
        if set(['KD_K', 'KD_D']).issubset(df_recent.columns):
            kd_vals = df_recent['KD_K']
            cross_80 = (kd_vals.shift(1) < 80) & (kd_vals >= 80)
            cross_20 = (kd_vals.shift(1) > 20) & (kd_vals <= 20)
            # KD 在 Panel 2，所以使用 axes[2]
            axes.scatter(df_recent.index[cross_80], kd_vals[cross_80], marker='^', color='red', s=85, zorder=10)  #這段不要改, 改了圖會跑掉
            axes.scatter(df_recent.index[cross_20], kd_vals[cross_20], marker='v', color='green', s=85, zorder=10)  #這段不要改, 改了圖會跑掉

        if 'RSI' in df_recent.columns:
            rsi_vals = df_recent['RSI']
            cross_70 = (rsi_vals.shift(1) < 70) & (rsi_vals >= 70)
            cross_30 = (rsi_vals.shift(1) > 30) & (rsi_vals <= 30)
            # RSI 在 Panel 3，所以使用 axes[3]
            axes.scatter(df_recent.index[cross_70], rsi_vals[cross_70], marker='^', color='red', s=85, zorder=10)  #這段不要改, 改了圖會跑掉
            axes.scatter(df_recent.index[cross_30], rsi_vals[cross_30], marker='v', color='green', s=85, zorder=10)  #這段不要改, 改了圖會跑掉
    except Exception as e:
        print(f'KD/RSI 標記層錯誤：{e}')

    fig.savefig(img_path)
    plt.close(fig)
    print(f"已產生：{img_path}")

def plot_all_k_lines():
    for t, name in stock_targets:
        code = t.upper()
        csv_file = f'output/{code}_indicators.csv'
        if os.path.exists(csv_file):
            # plot_k_line_with_indicators(csv_file, name)
            # 修改點：增加傳入 code (即 1326.TW)
            plot_k_line_with_indicators(csv_file, code, name)

def fetch_all_dividend_eps():
    result = []
    for ticker, name in stock_targets:
        # 僅針對台灣股市進行財報抓取
        if ticker.endswith('.TW') or ticker.endswith('.TWO') or ticker[:4].isdigit():
            code = ticker.upper().split('.')[0]
            try:
                data = get_eps_last5_years(code, name)
                if data:
                    result.extend(data)
            except Exception as e:
                print(f"[Goodinfo] {code} 抓取異常: {e}")
    
    os.makedirs("output", exist_ok=True)
    # 【修正 3】即使沒資料也產生 CSV，避免後續讀取報錯
    if not result:
        print('警告：無法取得任何股票殖利率/EPS資料')
        df = pd.DataFrame(columns=['ticker','name','year','dividend_yield','eps'])
    else:
        df = pd.DataFrame(result)
        for col in ['ticker','name','year','dividend_yield','eps']:
            if col not in df.columns:
                df[col] = None
        df = df[['ticker','name','year','dividend_yield','eps']]
        df = df.sort_values(['ticker','year'], ascending=[True,False])
    
    df.to_csv('output/stock_earning_summary.csv', index=False)
    print("已產生 5 年殖利率/EPS 報表")

def extract_recent_signals(csv_path):
    if not os.path.exists(csv_path): return []
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors='coerce', utc=True).tz_localize(None)
    else:
        df.index = df.index.tz_localize(None)

    today = datetime.now().date()
    last_week = today - timedelta(days=7)
    res = []
    
    if 'Close' not in df.columns: return res
    
    # KD 訊號
    if 'KD_K' in df.columns:
        kk = df['KD_K']
        cross_80 = (kk.shift(1)<80) & (kk>=80)
        cross_20 = (kk.shift(1)>20) & (kk<=20)
        for date in df.index[cross_80]:
            if last_week < date.date() <= today:
                res.append({'type':'KD_K 上穿80', 'date':str(date.date()), 'KD_K': round(kk.loc[date],2), 'Close': round(df.loc[date,'Close'],2)})
        for date in df.index[cross_20]:
            if last_week < date.date() <= today:
                res.append({'type':'KD_K 下穿20', 'date':str(date.date()), 'KD_K': round(kk.loc[date],2), 'Close': round(df.loc[date,'Close'],2)})
    
    # RSI 訊號
    if 'RSI' in df.columns:
        rsi = df['RSI']
        cross_70 = (rsi.shift(1)<70)&(rsi>=70)
        cross_30 = (rsi.shift(1)>30)&(rsi<=30)
        for date in df.index[cross_70]:
            if last_week < date.date() <= today:
                res.append({'type':'RSI 上穿70', 'date':str(date.date()), 'RSI': round(rsi.loc[date],2), 'Close': round(df.loc[date,'Close'],2)})
        for date in df.index[cross_30]:
            if last_week < date.date() <= today:
                res.append({'type':'RSI 下穿30', 'date':str(date.date()), 'RSI': round(rsi.loc[date],2), 'Close': round(df.loc[date,'Close'],2)})
    return res

def make_financial_summary_table(ticker, summary_file='output/stock_earning_summary.csv'):
    if not os.path.isfile(summary_file):
        return "_無法讀取資料_<br>"
    df = pd.read_csv(summary_file)
    tstr = ticker.upper().split('.')[0]
    df = df[df['ticker'].astype(str).str.upper() == tstr]
    df = df.sort_values('year', ascending=False).head(5)
    if df.empty:
        return "_無資料 (ETF無財報)_<br>"
    
    s = "<table border=1 cellpadding=4 style='border-collapse: collapse;'><tr><th>年度</th><th>殖利率(%)</th><th>配息</th><th>EPS</th></tr>"
    for _, row in df.iterrows():
        y = int(row['year']) if pd.notnull(row['year']) else "-"
        dy = row['dividend_yield'] if pd.notnull(row['dividend_yield']) else "-"
        eps = row['eps'] if pd.notnull(row['eps']) else "-"
        s += f"<tr><td>{y}</td><td>{dy}</td><td>{dy}</td><td>{eps}</td></tr>"
    s += "</table><br>"
    return s

#def make_single_stock_emailblock(ticker, name, chart_img_path, summary_table, recent_signals, cid):
def make_single_stock_emailblock(ticker, name, chart_img_path, summary_table, recent_signals, cid, pe_cid=None, pb_cid=None):
    html = f"<div style='border-bottom: 2px solid #eee; padding-bottom: 20px;'>"
    html += f"<h2>{ticker} {name}</h2>"
    html += f"<img src='cid:{cid[1:-1]}' style='width:100%; max-width:800px;'><br>"
    html += f"<b>📊 近5年殖利率/配息/EPS</b>{summary_table}"
    html += "<b>⚠️ 近一週警示訊號</b><br><table border=1 cellpadding=3 style='border-collapse: collapse;'><tr><th>類型</th><th>日期</th><th>K/RSI值</th><th>收盤</th></tr>"
    
    if recent_signals and recent_signals[0].get('type') != '本週無KD/RSI警示':
        for sig in recent_signals:
            val = sig.get('KD_K') if sig.get('KD_K') is not None else sig.get('RSI')
            html += f"<tr><td>{sig['type']}</td><td>{sig['date']}</td><td>{val}</td><td>{sig['Close']}</td></tr>"
    else:
        html += "<tr><td colspan=4>本週無特別訊號</td></tr>"
    html += "</table><br>"

    tw_code = ticker.split('.')[0]
    if tw_code.isdigit() and len(tw_code) >= 4:
        # 插入 Winvest 河流圖
        if pe_cid or pb_cid:
            winvest_url = f"https://winvest.tw/Stock/Symbol/Comment/{tw_code}"
            html += f"<h3><a href='{winvest_url}'>{ticker} {name} Winvest 價值河流圖</a></h3>"
            if pe_cid:
                html += f"<b>本益比河流圖:</b><br><img src='cid:{pe_cid[1:-1]}' style='width:100%; max-width:800px;'><br>"
            if pb_cid:
                html += f"<b>股價淨值比河流圖:</b><br><img src='cid:{pb_cid[1:-1]}' style='width:100%; max-width:800px;'><br>"
            html += "<br>"
        # 插入 Winvest 河流圖
        
        tw_url = f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={tw_code}"
        detail_html = get_gp_detail_html(tw_code)
        html += f"<h3>Goodinfo個股市況總覽</h3>"
        html += f"<a href='{tw_url}'>[👉 查看原網頁]</a><br>"
        html += f"{detail_html}"
    html += "</div>"
    return html

def send_inline_multi_stock_email(subject, to_email, all_blocks, all_imgs, from_email, app_password):
    if not app_password:
        print("錯誤：未設定 GMAIL_APP_PASSWORD 環境變數")
        return
    
    msg = MIMEMultipart("related")
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    
    html_body = f"<html><body>{''.join(all_blocks)}</body></html>"
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    
    for chart_img_path, cid in all_imgs:
        if os.path.exists(chart_img_path):
            with open(chart_img_path, "rb") as img:
                mime = MIMEImage(img.read())
                mime.add_header("Content-ID", f"<{cid[1:-1]}>")
                mime.add_header("Content-Disposition", "inline", filename=os.path.basename(chart_img_path))
                msg.attach(mime)
    
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(from_email, app_password)
        smtp.send_message(msg)
        smtp.quit()
        print(f"成功寄出報告至: {to_email}")
    except Exception as e:
        print(f"郵件發送失敗: {e}")

if __name__ == "__main__":
    # 1. 抓取資料
    for ticker, name in stock_targets:
        download_and_calc_indicators(ticker.upper(), name)
        time.sleep(1) # 增加延遲避免被 Yahoo 偵測為大量請求
    
    # 2. 繪製圖表
    plot_all_k_lines()
    
    # 3. 抓取基本面
    fetch_all_dividend_eps()
    
    # 4. 準備郵件內容
    from_email = "mingsyunapp@gmail.com"
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    to_email = "mingsyun@hotmail.com"
    
    all_blocks = []
    all_imgs = []
    
    for ticker, name in stock_targets:
        code = ticker.upper()
        chart_img = f"output/charts/{code}.png"
        csv = f"output/{code}_indicators.csv"
        
        summary_table = make_financial_summary_table(code)
        recent_signals = extract_recent_signals(csv)
        
        if not recent_signals:
            recent_signals = [{'type':'本週無KD/RSI警示', 'date':'-', 'KD_K':'-', 'RSI':'-', 'Close':'-'}]
            
        cid = make_msgid(domain="stock-report")

        # 抓取河流圖 (僅針對台灣股市)
        pe_img, pb_img = None, None
        pe_cid, pb_cid = None, None
        if code.split('.')[0].isdigit():
            pe_img, pb_img = capture_river_charts(code)
            if pe_img and os.path.exists(pe_img):
                pe_cid = make_msgid(domain="winvest-pe")
                all_imgs.append((pe_img, pe_cid))
            if pb_img and os.path.exists(pb_img):
                pb_cid = make_msgid(domain="winvest-pb")
                all_imgs.append((pb_img, pb_cid))
        # 抓取河流圖 (僅針對台灣股市)

        html = make_single_stock_emailblock(code, name, chart_img, summary_table, recent_signals, cid, pe_cid, pb_cid)
        #html = make_single_stock_emailblock(code, name, chart_img, summary_table, recent_signals, cid)
        
        all_blocks.append(html)
        all_imgs.append((chart_img, cid))
    
    # 5. 發送郵件
    if all_blocks:
        send_inline_multi_stock_email(
            subject=f"投資週報 - {datetime.now().strftime('%Y/%m/%d')}",
            to_email=to_email,
            all_blocks=all_blocks,
            all_imgs=all_imgs,
            from_email=from_email,
            app_password=app_password
        )
