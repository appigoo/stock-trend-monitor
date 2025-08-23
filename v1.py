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
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="股票監控儀表板", layout="wide")

load_dotenv()
REFRESH_INTERVAL = 144  # 秒，5 分鐘自動刷新
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# MACD 計算函數（省略，保持不變）
def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data["Close"].ewm(span=fast, adjust=False).mean()
    exp2 = data["Close"].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# RSI 計算函數（省略，保持不變）
def calculate_rsi(data, periods=14):
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 計算所有訊號的成功率（改進部分）
def calculate_signal_success_rate(data):
    # 計算下一交易日收盤價是否高於/低於當前收盤價
    data["Next_Close_Higher"] = data["Close"].shift(-1) > data["Close"]
    data["Next_Close_Lower"] = data["Close"].shift(-1) < data["Close"]
    
    # 定義賣出訊號列表（確保包含所有 14 種賣出訊號）
    sell_signals = [
        "High<Low", "MACD賣出", "EMA賣出", "價格趨勢賣出", "價格趨勢賣出(量)", 
        "價格趨勢賣出(量%)", "普通跳空(下)", "突破跳空(下)", "持續跳空(下)", 
        "衰竭跳空(下)", "連續向下賣出", "SMA50下降趨勢", "SMA50_200下降趨勢", 
        "新卖出信号"
    ]
    
    # 定義買入訊號列表（17 種，明確列出以便驗證）
    buy_signals = [
        "量價", "Low>High", "MACD買入", "EMA買入", "價格趨勢買入", "價格趨勢買入(量)", 
        "價格趨勢買入(量%)", "普通跳空(上)", "突破跳空(上)", "持續跳空(上)", 
        "衰竭跳空(上)", "連續向上買入", "SMA50上升趨勢", "SMA50_200上升趨勢", 
        "新买入信号", "新转折点", "关键转折点"
    ]
    
    # 獲取所有獨特的訊號類型
    all_signals = set()
    for signals in data["異動標記"].dropna():
        for signal in signals.split(", "):
            if signal:
                all_signals.add(signal)
    
    # 計算每種訊號的成功率
    success_rates = {}
    for signal in all_signals:
        signal_rows = data[data["異動標記"].str.contains(signal, na=False)]
        total_signals = len(signal_rows)
        if total_signals == 0:
            direction = "up" if signal in buy_signals else "down" if signal in sell_signals else "up"
            success_rates[signal] = {"success_rate": 0.0, "total_signals": 0, "direction": direction}
        else:
            if signal in sell_signals:
                # 賣出訊號：成功定義為下一交易日收盤價低於當前收盤價
                success_count = signal_rows["Next_Close_Lower"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "direction": "down"
                }
            else:
                # 買入訊號：成功定義為下一交易日收盤價高於當前收盤價
                success_count = signal_rows["Next_Close_Higher"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "direction": "up"
                }
        # 添加日誌以驗證訊號分類
        st.write(f"訊號 {signal} 分類為 {'買入' if success_rates[signal]['direction'] == 'up' else '賣出'}，成功率：{success_rates[signal]['success_rate']:.2f}%")
    
    return success_rates

# 郵件發送函數（省略，保持不變）
def send_email_alert(ticker, price_pct, volume_pct, low_high_signal=False, high_low_signal=False, 
                     macd_buy_signal=False, macd_sell_signal=False, ema_buy_signal=False, ema_sell_signal=False,
                     price_trend_buy_signal=False, price_trend_sell_signal=False,
                     price_trend_vol_buy_signal=False, price_trend_vol_sell_signal=False,
                     price_trend_vol_pct_buy_signal=False, price_trend_vol_pct_sell_signal=False,
                     gap_common_up=False, gap_common_down=False, gap_breakaway_up=False, gap_breakaway_down=False,
                     gap_runaway_up=False, gap_runaway_down=False, gap_exhaustion_up=False, gap_exhaustion_down=False,
                     continuous_up_buy_signal=False, continuous_down_sell_signal=False,
                     sma50_up_trend=False, sma50_down_trend=False,
                     sma50_200_up_trend=False, sma50_200_down_trend=False,
                     new_buy_signal=False, new_sell_signal=False, new_pivot_signal=False):
    pass  # （省略，保持不變）

# UI 設定（省略，保持不變）
period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
interval_options = ["1m", "5m", "2m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
percentile_options = [1, 5, 10, 20]

st.title("📊 股票監控儀表板（含異動提醒與 Email 通知 ✅）")
input_tickers = st.text_input("請輸入股票代號（逗號分隔）", value="TSLA, NIO, TSLL")
selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
selected_period = st.selectbox("選擇時間範圍", period_options, index=2)
selected_interval = st.selectbox("選擇資料間隔", interval_options, index=8)
PRICE_THRESHOLD = st.number_input("價格異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
VOLUME_THRESHOLD = st.number_input("成交量異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
PRICE_CHANGE_THRESHOLD = st.number_input("新轉折點 Price Change % 閾值 (%)", min_value=0.1, max_value=200.0, value=5.0, step=0.1)
VOLUME_CHANGE_THRESHOLD = st.number_input("新轉折點 Volume Change % 閾值 (%)", min_value=0.1, max_value=200.0, value=10.0, step=0.1)
GAP_THRESHOLD = st.number_input("跳空幅度閾值 (%)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)
CONTINUOUS_UP_THRESHOLD = st.number_input("連續上漲閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)
CONTINUOUS_DOWN_THRESHOLD = st.number_input("連續下跌閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)
PERCENTILE_THRESHOLD = st.selectbox("選擇 Price Change %、Volume Change %、Volume、股價漲跌幅 (%)、成交量變動幅 (%) 數據範圍 (%)", percentile_options, index=1)

placeholder = st.empty()

while True:
    with placeholder.container():
        st.subheader(f"⏱ 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for ticker in selected_tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period=selected_period, interval=selected_interval).reset_index()

                if data.empty or len(data) < 2:
                    st.warning(f"⚠️ {ticker} 無數據或數據不足（期間：{selected_period}，間隔：{selected_interval}），請嘗試其他時間範圍或間隔")
                    continue

                if "Date" in data.columns:
                    data = data.rename(columns={"Date": "Datetime"})
                elif "Datetime" not in data.columns:
                    st.warning(f"⚠️ {ticker} 數據缺少時間列，無法處理")
                    continue

                # 計算漲跌幅百分比（省略，保持不變）
                data["Price Change %"] = data["Close"].pct_change().round(4) * 100
                data["Volume Change %"] = data["Volume"].pct_change().round(4) * 100
                data["Close_Difference"] = data['Close'].diff().round(2)
                data["前5均價"] = data["Price Change %"].rolling(window=5).mean()
                data["前5均價ABS"] = abs(data["Price Change %"]).rolling(window=5).mean()
                data["前5均量"] = data["Volume"].rolling(window=5).mean()
                data["📈 股價漲跌幅 (%)"] = ((abs(data["Price Change %"]) - data["前5均價ABS"]) / data["前5均價ABS"]).round(4) * 100
                data["📊 成交量變動幅 (%)"] = ((data["Volume"] - data["前5均量"]) / data["前5均量"]).round(4) * 100

                # 計算 MACD、EMA、RSI、連續計數、SMA（省略，保持不變）
                data["MACD"], data["Signal"] = calculate_macd(data)
                data["EMA5"] = data["Close"].ewm(span=5, adjust=False).mean()
                data["EMA10"] = data["Close"].ewm(span=10, adjust=False).mean()
                data["RSI"] = calculate_rsi(data)
                data['Up'] = (data['Close'] > data['Close'].shift(1)).astype(int)
                data['Down'] = (data['Close'] < data['Close'].shift(1)).astype(int)
                data['Continuous_Up'] = data['Up'] * (data['Up'].groupby((data['Up'] == 0).cumsum()).cumcount() + 1)
                data['Continuous_Down'] = data['Down'] * (data['Down'].groupby((data['Down'] == 0).cumsum()).cumcount() + 1)
                data["SMA50"] = data["Close"].rolling(window=50).mean()
                data["SMA200"] = data["Close"].rolling(window=200).mean()

                # 標記訊號（省略，保持不變）
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
                    if index > 0 and row["Close"] > row["Open"] and row["Open"] > data["Close"].iloc[index-1]:
                        signals.append("📈 新买入信号")
                    if index > 0 and row["Close"] < row["Open"] and row["Open"] < data["Close"].iloc[index-1]:
                        signals.append("📉 新卖出信号")
                    if index > 0 and abs(row["Price Change %"]) > PRICE_CHANGE_THRESHOLD and abs(row["Volume Change %"]) > VOLUME_CHANGE_THRESHOLD:
                        signals.append("🔄 新转折点")
                    if len(signals) > 8:
                        signals.append(f"🔥 关键转折点 (信号数: {len(signals)})")
                    return ", ".join(signals) if signals else ""
                
                data["異動標記"] = [mark_signal(row, i) for i, row in data.iterrows()]

                # 當前資料（省略，保持不變）
                current_price = data["Close"].iloc[-1]
                previous_close = stock.info.get("previousClose", current_price)
                price_change = current_price - previous_close
                price_pct_change = (price_change / previous_close) * 100 if previous_close else 0
                last_volume = data["Volume"].iloc[-1]
                prev_volume = data["Volume"].iloc[-2] if len(data) > 1 else last_volume
                volume_change = last_volume - prev_volume
                volume_pct_change = (volume_change / prev_volume) * 100 if prev_volume else 0

                # 檢查訊號（省略，保持不變）
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
                                          data["Low"]. ILC[-1] < data["Low"].iloc[-2] and 
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
                                                  data["High"]. ILC[-1] < data["High"].iloc[-2] and 
                                                  data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                                                  data["Close"].iloc[-1] < data["Close"].iloc[-2] and 
                                                  data["Volume Change %"].iloc[-1] > 15)
                new_buy_signal = (len(data) > 1 and 
                                 data["Close"].iloc[-1] > data["Open"].iloc[-1] and 
                                 data["Open"].iloc[-1] > data["Close"].iloc[-2])
                new_sell_signal = (len(data) > 1 and 
                                  data["Close"].iloc[-1] < data["Open"].iloc[-1] and 
                                  data["Open"].iloc[-1] < data["Close"].iloc[-2])
                new_pivot_signal = (len(data) > 1 and 
                                   abs(data["Price Change %"].iloc[-1]) > PRICE_CHANGE_THRESHOLD and 
                                   abs(data["Volume Change %"].iloc[-1]) > VOLUME_CHANGE_THRESHOLD)
                
                # 跳空訊號（省略，保持不變）
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

                # 連續訊號和SMA訊號（省略，保持不變）
                continuous_up_buy_signal = data['Continuous_Up'].iloc[-1] >= CONTINUOUS_UP_THRESHOLD
                continuous_down_sell_signal = data['Continuous_Down'].iloc[-1] >= CONTINUOUS_DOWN_THRESHOLD
                sma50_up_trend = pd.notna(data["SMA50"].iloc[-1]) and data["Close"].iloc[-1] > data["SMA50"].iloc[-1]
                sma50_down_trend = pd.notna(data["SMA50"].iloc[-1]) and data["Close"]. ILC[-1] < data["SMA50"].iloc[-1]
                sma50_200_up_trend = pd.notna(data["SMA50"].iloc[-1]) and pd.notna(data["SMA200"].iloc[-1]) and \
                                     data["Close"].iloc[-1] > data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] > data["SMA200"].iloc[-1]
                sma50_200_down_trend = pd.notna(data["SMA50"].iloc[-1]) and pd.notna(data["SMA200"].iloc[-1]) and \
                                       data["Close"].iloc[-1] < data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] < data["SMA200"].iloc[-1]

                # 顯示當前資料
                st.metric(f"{ticker} 🟢 股價變動", f"${current_price:.2f}",
                          f"{price_change:.2f} ({price_pct_change:.2f}%)")
                st.metric(f"{ticker} 🔵 成交量變動", f"{last_volume:,}",
                          f"{volume_change:,} ({volume_pct_change:.2f}%)")

                # 計算並顯示所有訊號的成功率（改進部分）
                success_rates = calculate_signal_success_rate(data)
                
                # 分離買入和賣出訊號
                buy_signals = []
                sell_signals = []
                for signal, metrics in success_rates.items():
                    # 動態設置成功定義
                    success_definition = ("下一交易日收盤價高於目前收盤價" if metrics["direction"] == "up" 
                                         else "下一交易日收盤價低於目前收盤價")
                    signal_data = {
                        "訊號": signal,
                        "成功率 (%)": f"{metrics['success_rate']:.2f}%",
                        "觸發次數": metrics["total_signals"],
                        "成功定義": success_definition
                    }
                    if metrics["direction"] == "up":
                        buy_signals.append(signal_data)
                    elif metrics["direction"] == "down":
                        sell_signals.append(signal_data)

                # 顯示買入訊號成功率表格
                st.subheader(f"📈 {ticker} 買入訊號成功率")
                if buy_signals:
                    buy_signals_df = pd.DataFrame(buy_signals)
                    st.dataframe(
                        buy_signals_df,
                        use_container_width=True,
                        column_config={
                            "訊號": st.column_config.TextColumn("訊號", width="medium"),
                            "成功率 (%)": st.column_config.TextColumn("成功率 (%)", width="small"),
                            "觸發次數": st.column_config.NumberColumn("觸發次數", width="small"),
                            "成功定義": st.column_config.TextColumn("成功定義", width="large")
                        }
                    )
                    for signal_data in buy_signals:
                        signal = signal_data["訊號"]
                        success_rate = float(signal_data["成功率 (%)"].strip("%"))
                        total_signals = signal_data["觸發次數"]
                        st.metric(
                            f"{ticker} {signal} 成功率",
                            f"{success_rate:.2f}%",
                            f"基於 {total_signals} 次訊號 (上漲)"
                        )
                        if 0 < total_signals < 5:
                            st.warning(f"⚠️ {ticker} {signal} 樣本量過少（{total_signals} 次），成功率可能不穩定")
                else:
                    st.write("無買入訊號數據可顯示")

                # 顯示賣出訊號成功率表格
                st.subheader(f"📉 {ticker} 賣出訊號成功率")
                if sell_signals:
                    sell_signals_df = pd.DataFrame(sell_signals)
                    st.dataframe(
                        sell_signals_df,
                        use_container_width=True,
                        column_config={
                            "訊號": st.column_config.TextColumn("訊號", width="medium"),
                            "成功率 (%)": st.column_config.TextColumn("成功率 (%)", width="small"),
                            "觸發次數": st.column_config.NumberColumn("觸發次數", width="small"),
                            "成功定義": st.column_config.TextColumn("成功定義", width="large")
                        }
                    )
                    for signal_data in sell_signals:
                        signal = signal_data["訊號"]
                        success_rate = float(signal_data["成功率 (%)"].strip("%"))
                        total_signals = signal_data["觸發次數"]
                        st.metric(
                            f"{ticker} {signal} 成功率",
                            f"{success_rate:.2f}%",
                            f"基於 {total_signals} 次訊號 (下跌)"
                        )
                        if 0 < total_signals < 5:
                            st.warning(f"⚠️ {ticker} {signal} 樣本量過少（{total_signals} 次），成功率可能不穩定")
                else:
                    st.write("無賣出訊號數據可顯示")

                # 異動提醒和郵件通知（省略，保持不變）
                if (abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD) or \
                   low_high_signal or high_low_signal or macd_buy_signal or macd_sell_signal or \
                   ema_buy_signal or ema_sell_signal or price_trend_buy_signal or price_trend_sell_signal or \
                   price_trend_vol_buy_signal or price_trend_vol_sell_signal or \
                   price_trend_vol_pct_buy_signal or price_trend_vol_pct_sell_signal or \
                   gap_common_up or gap_common_down or gap_breakaway_up or gap_breakaway_down or \
                   gap_runaway_up or gap_runaway_down or gap_exhaustion_up or gap_exhaustion_down or \
                   continuous_up_buy_signal or continuous_down_sell_signal or \
                   sma50_up_trend or sma50_down_trend or sma50_200_up_trend or sma50_200_down_trend or \
                   new_buy_signal or new_sell_signal or new_pivot_signal:
                    alert_msg = f"{ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%"
                    # （省略警報訊息構建，保持不變）
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
                                    sma50_200_up_trend, sma50_200_down_trend,
                                    new_buy_signal, new_sell_signal, new_pivot_signal)

                # K 線圖、成交量圖、RSI 圖（省略，保持不變）
                st.subheader(f"📈 {ticker} K線圖與技術指標")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                    subplot_titles=(f"{ticker} K線與EMA", "成交量", "RSI"),
                                    vertical_spacing=0.1, row_heights=[0.5, 0.2, 0.3])
                fig.add_trace(go.Candlestick(x=data.tail(50)["Datetime"],
                                            open=data.tail(50)["Open"],
                                            high=data.tail(50)["High"],
                                            low=data.tail(50)["Low"],
                                            close=data.tail(50)["Close"],
                                            name="K線"), row=1, col=1)
                fig.add_trace(px.line(data.tail(50), x="Datetime", y="EMA5")["data"][0], row=1, col=1)
                fig.add_trace(px.line(data.tail(50), x="Datetime", y="EMA10")["data"][0], row=1, col=1)
                fig.add_bar(x=data.tail(50)["Datetime"], y=data.tail(50)["Volume"], 
                           name="成交量", opacity=0.5, row=2, col=1)
                fig.add_trace(px.line(data.tail(50), x="Datetime", y="RSI")["data"][0], row=3, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                for i in range(1, len(data.tail(50))):
                    idx = -50 + i
                    if (data["EMA5"].iloc[idx] > data["EMA10"].iloc[idx] and 
                        data["EMA5"].iloc[idx-1] <= data["EMA10"].iloc[idx-1]):
                        fig.add_annotation(x=data["Datetime"].iloc[idx], y=data["Close"].iloc[idx],
                                         text="📈 EMA買入", showarrow=True, arrowhead=2, ax=20, ay=-30, row=1, col=1)
                    elif (data["EMA5"].iloc[idx] < data["EMA10"].iloc[idx] and 
                          data["EMA5"].iloc[idx-1] >= data["EMA10"].iloc[idx-1]):
                        fig.add_annotation(x=data["Datetime"].iloc[idx], y=data["Close"].iloc[idx],
                                         text="📉 EMA賣出", showarrow=True, arrowhead=2, ax=20, ay=30, row=1, col=1)
                    if "关键转折点" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="star", size=12, color="yellow"),
                                       text=[f"🔥 转折点 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="关键转折点", row=1, col=1)
                    if "新买入信号" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="triangle-up", size=10, color="green"),
                                       text=[f"📈 新买入 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="bottom center", name="新买入信号", row=1, col=1)
                    if "新卖出信号" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="triangle-down", size=10, color="red"),
                                       text=[f"📉 新卖出 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="新卖出信号", row=1, col=1)
                    if "新转折点" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="star", size=10, color="purple"),
                                       text=[f"🔄 新转折点 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="新转折点", row=1, col=1)
                fig.update_layout(yaxis_title="價格", yaxis2_title="成交量", yaxis3_title="RSI", showlegend=True)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker}_{timestamp}")

                # 數據範圍表格（省略，保持不變）
                st.subheader(f"📊 {ticker} 前 {PERCENTILE_THRESHOLD}% 數據範圍")
                range_data = []
                sorted_price_changes = data["Price Change %"].dropna().sort_values(ascending=False)
                if len(sorted_price_changes) > 0:
                    top_percent_count = max(1, int(len(sorted_price_changes) * PERCENTILE_THRESHOLD / 100))
                    top_percent = sorted_price_changes.head(top_percent_count)
                    range_data.append({
                        "指標": "Price Change %",
                        "範圍類型": "最高到最低",
                        "最大值": f"{top_percent.max():.2f}%",
                        "最小值": f"{top_percent.min():.2f}%"
                    })
                # （省略其他數據範圍計算，保持不變）
                if range_data:
                    range_df = pd.DataFrame(range_data)
                    st.dataframe(
                        range_df,
                        use_container_width=True,
                        column_config={
                            "指標": st.column_config.TextColumn("指標", width="medium"),
                            "範圍類型": st.column_config.TextColumn("範圍類型", width="medium"),
                            "最大值": st.column_config.TextColumn("最大值", width="small"),
                            "最小值": st.column_config.TextColumn("最小值", width="small")
                        }
                    )
                else:
                    st.write("無有效數據範圍可顯示")

                # 歷史資料表格（省略，保持不變）
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

                # 下載按鈕（省略，保持不變）
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
