import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
import plotly.express as px

st.set_page_config(page_title="股票監控儀表板", layout="wide")

load_dotenv()
# 异动阈值设定
REFRESH_INTERVAL = 144  # 秒，5 分钟自动刷新

# Gmail 发信者帐号设置
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# MACD 计算函数
def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data["Close"].ewm(span=fast, adjust=False).mean()
    exp2 = data["Close"].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# 邮件发送函数
def send_email_alert(ticker, price_pct, volume_pct, low_high_signal=False, high_low_signal=False, 
                     macd_buy_signal=False, macd_sell_signal=False, ema_buy_signal=False, ema_sell_signal=False,
                     price_trend_buy_signal=False, price_trend_sell_signal=False,
                     price_trend_vol_buy_signal=False, price_trend_vol_sell_signal=False,
                     price_trend_vol_pct_buy_signal=False, price_trend_vol_pct_sell_signal=False,
                     gap_common_up=False, gap_common_down=False, gap_breakaway_up=False, gap_breakaway_down=False,
                     gap_runaway_up=False, gap_runaway_down=False, gap_exhaustion_up=False, gap_exhaustion_down=False,
                     continuous_up_buy_signal=False, continuous_down_sell_signal=False,
                     sma50_up_trend=False, sma50_down_trend=False,
                     sma50_200_up_trend=False, sma50_200_down_trend=False):
    subject = f"📣 股票異動通知：{ticker}"
    body = f"""
    股票代號：{ticker}
    股價變動：{price_pct:.2f}%
    成交量變動：{volume_pct:.2f}%
    """
    if low_high_signal:
        body += f"\n⚠️ 當前最低價高於前一時段最高價！"
    if high_low_signal:
        body += f"\n⚠️ 當前最高價低於前一時段最低價！"
    if macd_buy_signal:
        body += f"\n📈 MACD 買入訊號：MACD 線由負轉正！"
    if macd_sell_signal:
        body += f"\n📉 MACD 賣出訊號：MACD 線由正轉負！"
    if ema_buy_signal:
        body += f"\n📈 EMA 買入訊號：EMA5 上穿 EMA10，成交量放大！"
    if ema_sell_signal:
        body += f"\n📉 EMA 賣出訊號：EMA5 下破 EMA10，成交量放大！"
    if price_trend_buy_signal:
        body += f"\n📈 價格趨勢買入訊號：最高價、最低價、收盤價均上漲！"
    if price_trend_sell_signal:
        body += f"\n📉 價格趨勢賣出訊號：最高價、最低價、收盤價均下跌！"
    if price_trend_vol_buy_signal:
        body += f"\n📈 價格趨勢買入訊號（量）：最高價、最低價、收盤價均上漲且成交量放大！"
    if price_trend_vol_sell_signal:
        body += f"\n📉 價格趨勢賣出訊號（量）：最高價、最低價、收盤價均下跌且成交量放大！"
    if price_trend_vol_pct_buy_signal:
        body += f"\n📈 價格趨勢買入訊號（量%）：最高價、最低價、收盤價均上漲且成交量變化 > 15%！"
    if price_trend_vol_pct_sell_signal:
        body += f"\n📉 價格趨勢賣出訊號（量%）：最高價、最低價、收盤價均下跌且成交量變化 > 15%！"
    if gap_common_up:
        body += f"\n📈 普通跳空(上)：價格向上跳空，未伴隨明顯趨勢或成交量放大！"
    if gap_common_down:
        body += f"\n📉 普通跳空(下)：價格向下跳空，未伴隨明顯趨勢或成交量放大！"
    if gap_breakaway_up:
        body += f"\n📈 突破跳空(上)：價格向上跳空，突破前高且成交量放大！"
    if gap_breakaway_down:
        body += f"\n📉 突破跳空(下)：價格向下跳空，跌破前低且成交量放大！"
    if gap_runaway_up:
        body += f"\n📈 持續跳空(上)：價格向上跳空，處於上漲趨勢且成交量放大！"
    if gap_runaway_down:
        body += f"\n📉 持續跳空(下)：價格向下跳空，處於下跌趨勢且成交量放大！"
    if gap_exhaustion_up:
        body += f"\n📈 衰竭跳空(上)：價格向上跳空，趨勢末端且隨後價格下跌，成交量放大！"
    if gap_exhaustion_down:
        body += f"\n📉 衰竭跳空(下)：價格向下跳空，趨勢末端且隨後價格上漲，成交量放大！"
    if continuous_up_buy_signal:
        body += f"\n📈 連續向上策略買入訊號：至少連續上漲！"
    if continuous_down_sell_signal:
        body += f"\n📉 連續向下策略賣出訊號：至少連續下跌！"
    if sma50_up_trend:
        body += f"\n📈 SMA50 上升趨勢：當前價格高於 SMA50！"
    if sma50_down_trend:
        body += f"\n📉 SMA50 下降趨勢：當前價格低於 SMA50！"
    if sma50_200_up_trend:
        body += f"\n📈 SMA50_200 上升趨勢：當前價格高於 SMA50 且 SMA50 高於 SMA200！"
    if sma50_200_down_trend:
        body += f"\n📉 SMA50_200 下降趨勢：當前價格低於 SMA50 且 SMA50 低於 SMA200！"
    
    body += "\n系統偵測到異常變動，請立即查看市場情況。"
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        st.toast(f"📬 Email 已發送給 {RECIPIENT_EMAIL}")
    except Exception as e:
        st.error(f"Email 發送失敗：{e}")

# UI 设定
period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
interval_options = ["1m", "5m", "2m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]

st.title("📊 股票監控儀表板（含異動提醒與 Email 通知 ✅）")
input_tickers = st.text_input("請輸入股票代號（逗號分隔）", value="TSLA, NIO, TSLL")
selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
selected_period = st.selectbox("選擇時間範圍", period_options, index=1)
selected_interval = st.selectbox("選擇資料間隔", interval_options, index=1)
# 修改: 移除 window_size 滑动条
PRICE_THRESHOLD = st.number_input("價格異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
VOLUME_THRESHOLD = st.number_input("成交量異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
GAP_THRESHOLD = st.number_input("跳空幅度閾值 (%)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)
CONTINUOUS_UP_THRESHOLD = st.number_input("連續上漲閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)
CONTINUOUS_DOWN_THRESHOLD = st.number_input("連續下跌閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)

placeholder = st.empty()

while True:
    with placeholder.container():
        st.subheader(f"⏱ 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for ticker in selected_tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period=selected_period, interval=selected_interval).reset_index()

                # 检查数据是否为空并统一时间列名称
                if data.empty or len(data) < 2:
                    st.warning(f"⚠️ {ticker} 無數據或數據不足（期間：{selected_period}，間隔：{selected_interval}），請嘗試其他時間範圍或間隔")
                    continue

                # 统一时间列名称为 "Datetime"
                if "Date" in data.columns:
                    data = data.rename(columns={"Date": "Datetime"})
                elif "Datetime" not in data.columns:
                    st.warning(f"⚠️ {ticker} 數據缺少時間列，無法處理")
                    continue

                # 计算涨跌幅百分比
                data["Price Change %"] = data["Close"].pct_change().round(4) * 100
                data["Volume Change %"] = data["Volume"].pct_change().round(4) * 100
                data["Close_Difference"] = data['Close'].diff().round(2)
                
                # 修改: 固定前 5 周期平均收盘价与平均成交量
                data["前5均價"] = data["Price Change %"].rolling(window=5).mean()
                data["前5均價ABS"] = abs(data["Price Change %"]).rolling(window=5).mean()
                data["前5均量"] = data["Volume"].rolling(window=5).mean()
                data["📈 股價漲跌幅 (%)"] = ((abs(data["Price Change %"]) - data["前5均價ABS"]) / data["前5均價ABS"]).round(4) * 100
                data["📊 成交量變動幅 (%)"] = ((data["Volume"] - data["前5均量"]) / data["前5均量"]).round(4) * 100

                # 计算 MACD
                data["MACD"], data["Signal"] = calculate_macd(data)
                
                # 计算 EMA5 和 EMA10
                data["EMA5"] = data["Close"].ewm(span=5, adjust=False).mean()
                data["EMA10"] = data["Close"].ewm(span=10, adjust=False).mean()
                
                # 计算连续上涨/下跌计数
                data['Up'] = (data['Close'] > data['Close'].shift(1)).astype(int)
                data['Down'] = (data['Close'] < data['Close'].shift(1)).astype(int)
                data['Continuous_Up'] = data['Up'] * (data['Up'].groupby((data['Up'] == 0).cumsum()).cumcount() + 1)
                data['Continuous_Down'] = data['Down'] * (data['Down'].groupby((data['Down'] == 0).cumsum()).cumcount() + 1)
                
                # 计算 SMA50 和 SMA200
                data["SMA50"] = data["Close"].rolling(window=50).mean()
                data["SMA200"] = data["Close"].rolling(window=200).mean()
                
                # 标记量价异动、Low > High、High < Low、MACD、EMA、价格趋势及带成交量条件的价格趋势信号
                def mark_signal(row, index):
                    signals = []
                    if abs(row["📈 股價漲跌幅 (%)"]) >= PRICE_THRESHOLD and abs(row["📊 成交量變動幅 (%)"]) >= VOLUME_THRESHOLD:
                        signals.append("✅ 量價")
                    if index > 0 and row["Low"] > data["High"].iloc[index-1]:
                        signals.append("📈 Low>High")
                    if index > 0 and row["High"] < data["Low"].iloc[index-1]:
                        signals.append("📉 High<Low")
                    if index > 0 and row["MACD"] > 0 and data["MACD"].iloc[index-1] <= 0:
                        signals.append("📈 MACD買入")
                    if index > 0 and row["MACD"] <= 0 and data["MACD"].iloc[index-1] > 0:
                        signals.append("📉 MACD賣出")
                    if (index > 0 and row["EMA5"] > row["EMA10"] and 
                        data["EMA5"].iloc[index-1] <= data["EMA10"].iloc[index-1] and 
                        row["Volume"] > data["Volume"].iloc[index-1]):
                        signals.append("📈 EMA買入")
                    if (index > 0 and row["EMA5"] < row["EMA10"] and 
                        data["EMA5"].iloc[index-1] >= data["EMA10"].iloc[index-1] and 
                        row["Volume"] > data["Volume"].iloc[index-1]):
                        signals.append("📉 EMA賣出")
                    if (index > 0 and row["High"] > data["High"].iloc[index-1] and 
                        row["Low"] > data["Low"].iloc[index-1] and 
                        row["Close"] > data["Close"].iloc[index-1]):
                        signals.append("📈 價格趨勢買入")
                    if (index > 0 and row["High"] < data["High"].iloc[index-1] and 
                        row["Low"] < data["Low"].iloc[index-1] and 
                        row["Close"] < data["Close"].iloc[index-1]):
                        signals.append("📉 價格趨勢賣出")
                    if (index > 0 and row["High"] > data["High"].iloc[index-1] and 
                        row["Low"] > data["Low"].iloc[index-1] and 
                        row["Close"] > data["Close"].iloc[index-1] and 
                        row["Volume"] > data["前5均量"].iloc[index]):
                        signals.append("📈 價格趨勢買入(量)")
                    if (index > 0 and row["High"] < data["High"].iloc[index-1] and 
                        row["Low"] < data["Low"].iloc[index-1] and 
                        row["Close"] < data["Close"].iloc[index-1] and 
                        row["Volume"] > data["前5均量"].iloc[index]):
                        signals.append("📉 價格趨勢賣出(量)")
                    if (index > 0 and row["High"] > data["High"].iloc[index-1] and 
                        row["Low"] > data["Low"].iloc[index-1] and 
                        row["Close"] > data["Close"].iloc[index-1] and 
                        row["Volume Change %"] > 15):
                        signals.append("📈 價格趨勢買入(量%)")
                    if (index > 0 and row["High"] < data["High"].iloc[index-1] and 
                        row["Low"] < data["Low"].iloc[index-1] and 
                        row["Close"] < data["Close"].iloc[index-1] and 
                        row["Volume Change %"] > 15):
                        signals.append("📉 價格趨勢賣出(量%)")
                    if index > 0:
                        gap_pct = ((row["Open"] - data["Close"].iloc[index-1]) / data["Close"].iloc[index-1]) * 100
                        is_up_gap = gap_pct > GAP_THRESHOLD
                        is_down_gap = gap_pct < -GAP_THRESHOLD
                        if is_up_gap or is_down_gap:
                            trend = data["Close"].iloc[index-5:index].mean() if index >= 5 else 0
                            prev_trend = data["Close"].iloc[index-6:index-1].mean() if index >= 6 else trend
                            is_up_trend = row["Close"] > trend and trend > prev_trend
                            is_down_trend = row["Close"] < trend and trend < prev_trend
                            is_high_volume = row["Volume"] > data["前5均量"].iloc[index]
                            is_price_reversal = (index < len(data) - 1 and
                                                ((is_up_gap and data["Close"].iloc[index+1] < row["Close"]) or
                                                 (is_down_gap and data["Close"].iloc[index+1] > row["Close"])))
                            if is_up_gap:
                                if is_price_reversal and is_high_volume:
                                    signals.append("📈 衰竭跳空(上)")
                                elif is_up_trend and is_high_volume:
                                    signals.append("📈 持續跳空(上)")
                                elif row["High"] > data["High"].iloc[index-1:index].max() and is_high_volume:
                                    signals.append("📈 突破跳空(上)")
                                else:
                                    signals.append("📈 普通跳空(上)")
                            elif is_down_gap:
                                if is_price_reversal and is_high_volume:
                                    signals.append("📉 衰竭跳空(下)")
                                elif is_down_trend and is_high_volume:
                                    signals.append("📉 持續跳空(下)")
                                elif row["Low"] < data["Low"].iloc[index-1:index].min() and is_high_volume:
                                    signals.append("📉 突破跳空(下)")
                                else:
                                    signals.append("📉 普通跳空(下)")
                    if row['Continuous_Up'] >= CONTINUOUS_UP_THRESHOLD:
                        signals.append("📈 連續向上買入")
                    if row['Continuous_Down'] >= CONTINUOUS_DOWN_THRESHOLD:
                        signals.append("📉 連續向下賣出")
                    if pd.notna(row["SMA50"]):
                        if row["Close"] > row["SMA50"]:
                            signals.append("📈 SMA50上升趨勢")
                        elif row["Close"] < row["SMA50"]:
                            signals.append("📉 SMA50下降趨勢")
                    if pd.notna(row["SMA50"]) and pd.notna(row["SMA200"]):
                        if row["Close"] > row["SMA50"] and row["SMA50"] > row["SMA200"]:
                            signals.append("📈 SMA50_200上升趨勢")
                        elif row["Close"] < row["SMA50"] and row["SMA50"] < row["SMA200"]:
                            signals.append("📉 SMA50_200下降趨勢")
                    return ", ".join(signals) if signals else ""
                
                data["異動標記"] = [mark_signal(row, i) for i, row in data.iterrows()]

                # 当前资料
                current_price = data["Close"].iloc[-1]
                previous_close = stock.info.get("previousClose", current_price)
                price_change = current_price - previous_close
                price_pct_change = (price_change / previous_close) * 100 if previous_close else 0

                last_volume = data["Volume"].iloc[-1]
                prev_volume = data["Volume"].iloc[-2] if len(data) > 1 else last_volume
                volume_change = last_volume - prev_volume
                volume_pct_change = (volume_change / prev_volume) * 100 if prev_volume else 0

                # 检查 Low > High、High < Low、MACD、EMA、价格趋势及带成交量条件的价格趋势信号
                low_high_signal = len(data) > 1 and data["Low"].iloc[-1] > data["High"].iloc[-2]
                high_low_signal = len(data) > 1 and data["High"].iloc[-1] < data["Low"].iloc[-2]
                macd_buy_signal = len(data) > 1 and data["MACD"].iloc[-1] > 0 and data["MACD"].iloc[-2] <= 0
                macd_sell_signal = len(data) > 1 and data["MACD"].iloc[-1] <= 0 and data["MACD"].iloc[-2] > 0
                ema_buy_signal = (len(data) > 1 and 
                                 data["EMA5"].iloc[-1] > data["EMA10"].iloc[-1] and 
                                 data["EMA5"].iloc[-2] <= data["EMA10"].iloc[-2] and 
                                 data["Volume"].iloc[-1] > data["Volume"].iloc[-2])
                ema_sell_signal = (len(data) > 1 and 
                                  data["EMA5"].iloc[-1] < data["EMA10"].iloc[-1] and 
                                  data["EMA5"].iloc[-2] >= data["EMA10"].iloc[-2] and 
                                  data["Volume"].iloc[-1] > data["Volume"].iloc[-2])
                price_trend_buy_signal = (len(data) > 1 and 
                                         data["High"].iloc[-1] > data["High"].iloc[-2] and 
                                         data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                                         data["Close"].iloc[-1] > data["Close"].iloc[-2])
                price_trend_sell_signal = (len(data) > 1 and 
                                          data["High"].iloc[-1] < data["High"].iloc[-2] and 
                                          data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                                          data["Close"].iloc[-1] < data["Close"].iloc[-2])
                price_trend_vol_buy_signal = (len(data) > 1 and 
                                             data["High"].iloc[-1] > data["High"].iloc[-2] and 
                                             data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                                             data["Close"].iloc[-1] > data["Close"].iloc[-2] and 
                                             data["Volume"].iloc[-1] > data["前5均量"].iloc[-1])
                price_trend_vol_sell_signal = (len(data) > 1 and 
                                              data["High"].iloc[-1] < data["High"].iloc[-2] and 
                                              data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                                              data["Close"].iloc[-1] < data["Close"].iloc[-2] and 
                                              data["Volume"].iloc[-1] > data["前5均量"].iloc[-1])
                price_trend_vol_pct_buy_signal = (len(data) > 1 and 
                                                 data["High"].iloc[-1] > data["High"].iloc[-2] and 
                                                 data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                                                 data["Close"].iloc[-1] > data["Close"].iloc[-2] and 
                                                 data["Volume Change %"].iloc[-1] > 15)
                price_trend_vol_pct_sell_signal = (len(data) > 1 and 
                                                  data["High"].iloc[-1] < data["High"].iloc[-2] and 
                                                  data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                                                  data["Close"].iloc[-1] < data["Close"].iloc[-2] and 
                                                  data["Volume Change %"].iloc[-1] > 15)
                
                # 新增: 跳空信号检测
                gap_common_up = False
                gap_common_down = False
                gap_breakaway_up = False
                gap_breakaway_down = False
                gap_runaway_up = False
                gap_runaway_down = False
                gap_exhaustion_up = False
                gap_exhaustion_down = False
                if len(data) > 1:
                    gap_pct = ((data["Open"].iloc[-1] - data["Close"].iloc[-2]) / data["Close"].iloc[-2]) * 100
                    is_up_gap = gap_pct > GAP_THRESHOLD
                    is_down_gap = gap_pct < -GAP_THRESHOLD
                    if is_up_gap or is_down_gap:
                        trend = data["Close"].iloc[-5:].mean() if len(data) >= 5 else 0
                        prev_trend = data["Close"].iloc[-6:-1].mean() if len(data) >= 6 else trend
                        is_up_trend = data["Close"].iloc[-1] > trend and trend > prev_trend
                        is_down_trend = data["Close"].iloc[-1] < trend and trend < prev_trend
                        is_high_volume = data["Volume"].iloc[-1] > data["前5均量"].iloc[-1]
                        is_price_reversal = (len(data) > 2 and
                                            ((is_up_gap and data["Close"].iloc[-1] < data["Close"].iloc[-2]) or
                                             (is_down_gap and data["Close"].iloc[-1] > data["Close"].iloc[-2])))
                        if is_up_gap:
                            if is_price_reversal and is_high_volume:
                                gap_exhaustion_up = True
                            elif is_up_trend and is_high_volume:
                                gap_runaway_up = True
                            elif data["High"].iloc[-1] > data["High"].iloc[-2:-1].max() and is_high_volume:
                                gap_breakaway_up = True
                            else:
                                gap_common_up = True
                        elif is_down_gap:
                            if is_price_reversal and is_high_volume:
                                gap_exhaustion_down = True
                            elif is_down_trend and is_high_volume:
                                gap_runaway_down = True
                            elif data["Low"].iloc[-1] < data["Low"].iloc[-2:-1].min() and is_high_volume:
                                gap_breakaway_down = True
                            else:
                                gap_common_down = True

                # 新增: 连续向上/向下信号检测
                continuous_up_buy_signal = data['Continuous_Up'].iloc[-1] >= CONTINUOUS_UP_THRESHOLD
                continuous_down_sell_signal = data['Continuous_Down'].iloc[-1] >= CONTINUOUS_DOWN_THRESHOLD

                # 新增: SMA趋势信号检测
                sma50_up_trend = False
                sma50_down_trend = False
                sma50_200_up_trend = False
                sma50_200_down_trend = False
                if pd.notna(data["SMA50"].iloc[-1]):
                    if data["Close"].iloc[-1] > data["SMA50"].iloc[-1]:
                        sma50_up_trend = True
                    elif data["Close"].iloc[-1] < data["SMA50"].iloc[-1]:
                        sma50_down_trend = True
                if pd.notna(data["SMA50"].iloc[-1]) and pd.notna(data["SMA200"].iloc[-1]):
                    if data["Close"].iloc[-1] > data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] > data["SMA200"].iloc[-1]:
                        sma50_200_up_trend = True
                    elif data["Close"].iloc[-1] < data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] < data["SMA200"].iloc[-1]:
                        sma50_200_down_trend = True

                # 显示当前资料
                st.metric(f"{ticker} 🟢 股價變動", f"${current_price:.2f}",
                          f"{price_change:.2f} ({price_pct_change:.2f}%)")
                st.metric(f"{ticker} 🔵 成交量變動", f"{last_volume:,}",
                          f"{volume_change:,} ({volume_pct_change:.2f}%)")

                # 异动提醒 + Email 推播，包含基于成交量变化百分比的价格趋势信号
                if (abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD) or low_high_signal or high_low_signal or macd_buy_signal or macd_sell_signal or ema_buy_signal or ema_sell_signal or price_trend_buy_signal or price_trend_sell_signal or price_trend_vol_buy_signal or price_trend_vol_sell_signal or price_trend_vol_pct_buy_signal or price_trend_vol_pct_sell_signal or gap_common_up or gap_common_down or gap_breakaway_up or gap_breakaway_down or gap_runaway_up or gap_runaway_down or gap_exhaustion_up or gap_exhaustion_down or continuous_up_buy_signal or continuous_down_sell_signal or sma50_up_trend or sma50_down_trend or sma50_200_up_trend or sma50_200_down_trend:
                    alert_msg = f"{ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%"
                    if low_high_signal:
                        alert_msg += "，當前最低價高於前一時段最高價"
                    if high_low_signal:
                        alert_msg += "，當前最高價低於前一時段最低價"
                    if macd_buy_signal:
                        alert_msg += "，MACD 買入訊號（MACD 線由負轉正）"
                    if macd_sell_signal:
                        alert_msg += "，MACD 賣出訊號（MACD 線由正轉負）"
                    if ema_buy_signal:
                        alert_msg += "，EMA 買入訊號（EMA5 上穿 EMA10，成交量放大）"
                    if ema_sell_signal:
                        alert_msg += "，EMA 賣出訊號（EMA5 下破 EMA10，成交量放大）"
                    if price_trend_buy_signal:
                        alert_msg += "，價格趨勢買入訊號（最高價、最低價、收盤價均上漲）"
                    if price_trend_sell_signal:
                        alert_msg += "，價格趨勢賣出訊號（最高價、最低價、收盤價均下跌）"
                    if price_trend_vol_buy_signal:
                        alert_msg += "，價格趨勢買入訊號（量）（最高價、最低價、收盤價均上漲且成交量放大）"
                    if price_trend_vol_sell_signal:
                        alert_msg += "，價格趨勢賣出訊號（量）（最高價、最低價、收盤價均下跌且成交量放大）"
                    if price_trend_vol_pct_buy_signal:
                        alert_msg += "，價格趨勢買入訊號（量%）（最高價、最低價、收盤價均上漲且成交量變化 > 15%）"
                    if price_trend_vol_pct_sell_signal:
                        alert_msg += "，價格趨勢賣出訊號（量%）（最高價、最低價、收盤價均下跌且成交量變化 > 15%）"
                    if gap_common_up:
                        alert_msg += "，普通跳空(上)（價格向上跳空，未伴隨明顯趨勢或成交量放大）"
                    if gap_common_down:
                        alert_msg += "，普通跳空(下)（價格向下跳空，未伴隨明顯趨勢或成交量放大）"
                    if gap_breakaway_up:
                        alert_msg += "，突破跳空(上)（價格向上跳空，突破前高且成交量放大）"
                    if gap_breakaway_down:
                        alert_msg += "，突破跳空(下)（價格向下跳空，跌破前低且成交量放大）"
                    if gap_runaway_up:
                        alert_msg += "，持續跳空(上)（價格向上跳空，處於上漲趨勢且成交量放大）"
                    if gap_runaway_down:
                        alert_msg += "，持續跳空(下)（價格向下跳空，處於下跌趨勢且成交量放大）"
                    if gap_exhaustion_up:
                        alert_msg += "，衰竭跳空(上)（價格向上跳空，趨勢末端且隨後價格下跌，成交量放大）"
                    if gap_exhaustion_down:
                        alert_msg += "，衰竭跳空(下)（價格向下跳空，趨勢末端且隨後價格上漲，成交量放大）"
                    if continuous_up_buy_signal:
                        alert_msg += f"，連續向上策略買入訊號（至少連續 {CONTINUOUS_UP_THRESHOLD} 根K線上漲）"
                    if continuous_down_sell_signal:
                        alert_msg += f"，連續向下策略賣出訊號（至少連續 {CONTINUOUS_DOWN_THRESHOLD} 根K線下跌）"
                    if sma50_up_trend:
                        alert_msg += "，SMA50 上升趨勢（當前價格高於 SMA50）"
                    if sma50_down_trend:
                        alert_msg += "，SMA50 下降趨勢（當前價格低於 SMA50）"
                    if sma50_200_up_trend:
                        alert_msg += "，SMA50_200 上升趨勢（當前價格高於 SMA50 且 SMA50 高於 SMA200）"
                    if sma50_200_down_trend:
                        alert_msg += "，SMA50_200 下降趨勢（當前價格低於 SMA50 且 SMA50 低於 SMA200）"
                    st.warning(f"📣 {alert_msg}")
                    st.toast(f"📣 {alert_msg}")
                    send_email_alert(ticker, price_pct_change, volume_pct_change, low_high_signal, high_low_signal, 
                                    macd_buy_signal, macd_sell_signal, ema_buy_signal, ema_sell_signal, 
                                    price_trend_buy_signal, price_trend_sell_signal,
                                    price_trend_vol_buy_signal, price_trend_vol_sell_signal,
                                    price_trend_vol_pct_buy_signal, price_trend_vol_pct_sell_signal,
                                    gap_common_up, gap_common_down, gap_breakaway_up, gap_breakaway_down,
                                    gap_runaway_up, gap_runaway_down, gap_exhaustion_up, gap_exhaustion_down,
                                    continuous_up_buy_signal, continuous_down_sell_signal,
                                    sma50_up_trend, sma50_down_trend,
                                    sma50_200_up_trend, sma50_200_down_trend)

                # 添加价格和成交量折线图
                st.subheader(f"📈 {ticker} 價格與成交量趨勢")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                fig = px.line(data.tail(50), x="Datetime", y=["Close", "Volume"], 
                             title=f"{ticker} 價格與成交量",
                             labels={"Close": "價格", "Volume": "成交量"},
                             render_mode="svg")
                fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="成交量"))
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker}_{timestamp}")

                # 显示含异动标记的历史资料
                st.subheader(f"📋 歷史資料：{ticker}")
                display_data = data[["Datetime","Low","High", "Close", "Volume", "Price Change %", 
                                     "Volume Change %", "📈 股價漲跌幅 (%)", 
                                     "📊 成交量變動幅 (%)","Close_Difference", "異動標記"]].tail(15)
                if not display_data.empty:
                    st.dataframe(
                        display_data,
                        height=600,
                        use_container_width=True,
                        column_config={
                            "異動標記": st.column_config.TextColumn(width="large")
                        }
                    )
                else:
                    st.warning(f"⚠️ {ticker} 歷史數據表無內容可顯示")

                # 添加下载按钮
                csv = data.to_csv(index=False)
                st.download_button(
                    label=f"📥 下載 {ticker} 數據 (CSV)",
                    data=csv,
                    file_name=f"{ticker}_數據_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.warning(f"⚠️ 無法取得 {ticker} 的資料：{e}，將跳過此股票")
                continue

        st.markdown("---")
        st.info("📡 頁面將在 5 分鐘後自動刷新...")

    time.sleep(REFRESH_INTERVAL)
    placeholder.empty()
