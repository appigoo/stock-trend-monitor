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

# MACD 计算函数
def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data["Close"].ewm(span=fast, adjust=False).mean()
    exp2 = data["Close"].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# RSI 计算函数
def calculate_rsi(data, periods=14):
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 计算所有信号的成功率
def calculate_signal_success_rate(data):
    data["Next_Close_Higher"] = data["Close"].shift(-1) > data["Close"]
    data["Next_Close_Lower"] = data["Close"].shift(-1) < data["Close"]
    sell_signals = [
        "High<Low", "MACD賣出", "EMA賣出", "價格趨勢賣出", "價格趨勢賣出(量)", 
        "價格趨勢賣出(量%)", "普通跳空(下)", "突破跳空(下)", "持續跳空(下)", 
        "衰竭跳空(下)", "連續向下賣出", "SMA50下降趨勢", "SMA50_200下降趨勢", 
        "新卖出信号"
    ]
    all_signals = set()
    for signals in data["異動標記"].dropna():
        for signal in signals.split(", "):
            if signal:
                all_signals.add(signal)
    success_rates = {}
    for signal in all_signals:
        signal_rows = data[data["異動標記"].str.contains(signal, na=False)]
        total_signals = len(signal_rows)
        if total_signals == 0:
            success_rates[signal] = {"success_rate": 0.0, "total_signals": 0, "direction": "up" if signal not in sell_signals else "down"}
        else:
            if signal in sell_signals:
                success_count = signal_rows["Next_Close_Lower"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "direction": "down"
                }
            else:
                success_count = signal_rows["Next_Close_Higher"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "direction": "up"
                }
    return success_rates

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
                     sma50_200_up_trend=False, sma50_200_down_trend=False,
                     new_buy_signal=False, new_sell_signal=False, new_pivot_signal=False):
    subject = f"📣 股票異動通知：{ticker}"
    body = f"""
    股票代號：{ticker}
    股價變動：{price_pct:.2f}%
    成交量變動：{volume_pct:.2f}%
    """
    if low_high_signal:
        body += f"\n📈 Low>High"
    if high_low_signal:
        body += f"\n📉 High<Low"
    if macd_buy_signal:
        body += f"\n📈 MACD買入"
    if macd_sell_signal:
        body += f"\n📉 MACD賣出"
    if ema_buy_signal:
        body += f"\n📈 EMA買入"
    if ema_sell_signal:
        body += f"\n📉 EMA賣出"
    if price_trend_buy_signal:
        body += f"\n📈 價格趨勢買入"
    if price_trend_sell_signal:
        body += f"\n📉 價格趨勢賣出"
    if price_trend_vol_buy_signal:
        body += f"\n📈 價格趨勢買入(量)"
    if price_trend_vol_sell_signal:
        body += f"\n📉 價格趨勢賣出(量)"
    if price_trend_vol_pct_buy_signal:
        body += f"\n📈 價格趨勢買入(量%)"
    if price_trend_vol_pct_sell_signal:
        body += f"\n📉 價格趨勢賣出(量%)"
    if gap_common_up:
        body += f"\n📈 普通跳空(上)"
    if gap_common_down:
        body += f"\n📉 普通跳空(下)"
    if gap_breakaway_up:
        body += f"\n📈 突破跳空(上)"
    if gap_breakaway_down:
        body += f"\n📉 突破跳空(下)"
    if gap_runaway_up:
        body += f"\n📈 持續跳空(上)"
    if gap_runaway_down:
        body += f"\n📉 持續跳空(下)"
    if gap_exhaustion_up:
        body += f"\n📈 衰竭跳空(上)"
    if gap_exhaustion_down:
        body += f"\n📉 衰竭跳空(下)"
    if continuous_up_buy_signal:
        body += f"\n📈 連續向上買入"
    if continuous_down_sell_signal:
        body += f"\n📉 連續向下賣出"
    if sma50_up_trend:
        body += f"\n📈 SMA50上升趨勢"
    if sma50_down_trend:
        body += f"\n📉 SMA50下降趨勢"
    if sma50_200_up_trend:
        body += f"\n📈 SMA50_200上升趨勢"
    if sma50_200_down_trend:
        body += f"\n📉 SMA50_200下降趨勢"
    if new_buy_signal:
        body += f"\n📈 新买入信号"
    if new_sell_signal:
        body += f"\n📉 新卖出信号"
    if new_pivot_signal:
        body += f"\n🔄 新转折点"
    
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
        st.success(f"📬 Email 已發送給 {RECIPIENT_EMAIL}")
    except Exception as e:
        st.error(f"Email 發送失敗：{e}")

# UI 设定
st.title("📊 股票監控儀表板")
st.markdown("实时监控股票异动信号，包含技术指标和邮件通知功能。", help="数据来源于 yfinance，刷新间隔可自定义。")

with st.sidebar:
    st.header("⚙️ 参数设置")
    input_tickers = st.text_input("股票代号（逗号分隔）", value="TSLA, NIO, TSLL", help="输入股票代码，如 TSLA, AAPL")
    selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
    
    period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
    selected_period = st.selectbox("时间范围", period_options, index=2, help="选择数据的历史时间范围")
    
    interval_options = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
    selected_interval = st.selectbox("数据间隔", interval_options, index=8, help="选择数据的K线间隔")
    
    refresh_options = [30, 60, 90, 144, 180, 210, 244]
    REFRESH_INTERVAL = st.selectbox("刷新间隔 (秒)", refresh_options, index=3, help="页面自动刷新间隔，单位为秒")
    
    PRICE_THRESHOLD = st.number_input("价格异动阈值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
    VOLUME_THRESHOLD = st.number_input("成交量异动阈值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
    PRICE_CHANGE_THRESHOLD = st.number_input("新转折点 Price Change % 阈值 (%)", min_value=0.1, max_value=200.0, value=5.0, step=0.1)
    VOLUME_CHANGE_THRESHOLD = st.number_input("新转折点 Volume Change % 阈值 (%)", min_value=0.1, max_value=200.0, value=10.0, step=0.1)
    GAP_THRESHOLD = st.number_input("跳空幅度阈值 (%)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)
    CONTINUOUS_UP_THRESHOLD = st.number_input("连续上涨阈值 (根K线)", min_value=1, max_value=20, value=3, step=1)
    CONTINUOUS_DOWN_THRESHOLD = st.number_input("连续下跌阈值 (根K线)", min_value=1, max_value=20, value=3, step=1)
    percentile_options = [1, 5, 10, 20]
    PERCENTILE_THRESHOLD = st.selectbox("数据范围 (%)", percentile_options, index=1, help="选择指标的前 X% 数据范围")

placeholder = st.empty()

while True:
    with placeholder.container():
        st.markdown(f"**⏱ 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
        
        for ticker in selected_tickers:
            with st.container():
                st.subheader(f"📈 {ticker} 实时数据")
                try:
                    stock = yf.Ticker(ticker)
                    data = stock.history(period=selected_period, interval=selected_interval).reset_index()

                    # 检查数据是否为空并统一时间列名称
                    if data.empty or len(data) < 2:
                        st.warning(f"⚠️ {ticker} 无数据或数据不足（期间：{selected_period}，间隔：{selected_interval}）")
                        continue

                    if "Date" in data.columns:
                        data = data.rename(columns={"Date": "Datetime"})
                    elif "Datetime" not in data.columns:
                        st.warning(f"⚠️ {ticker} 数据缺少时间列")
                        continue

                    # 计算涨跌幅百分比
                    data["Price Change %"] = data["Close"].pct_change().round(4) * 100
                    data["Volume Change %"] = data["Volume"].pct_change().round(4) * 100
                    data["Close_Difference"] = data['Close'].diff().round(2)
                    data["前5均價"] = data["Price Change %"].rolling(window=5).mean()
                    data["前5均價ABS"] = abs(data["Price Change %"]).rolling(window=5).mean()
                    data["前5均量"] = data["Volume"].rolling(window=5).mean()
                    data["📈 股價漲跌幅 (%)"] = ((abs(data["Price Change %"]) - data["前5均價ABS"]) / data["前5均價ABS"]).round(4) * 100
                    data["📊 成交量變動幅 (%)"] = ((data["Volume"] - data["前5均量"]) / data["前5均量"]).round(4) * 100

                    # 计算 MACD、EMA、RSI、连续趋势、SMA
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

                    # 标记信号
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

                    # 当前数据
                    current_price = data["Close"].iloc[-1]
                    previous_close = stock.info.get("previousClose", current_price)
                    price_change = current_price - previous_close
                    price_pct_change = (price_change / previous_close) * 100 if previous_close else 0
                    last_volume = data["Volume"].iloc[-1]
                    prev_volume = data["Volume"].iloc[-2] if len(data) > 1 else last_volume
                    volume_change = last_volume - prev_volume
                    volume_pct_change = (volume_change / prev_volume) * 100 if prev_volume else 0

                    # 信号检测
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
                    new_buy_signal = (len(data) > 1 and 
                                     data["Close"].iloc[-1] > data["Open"].iloc[-1] and 
                                     data["Open"].iloc[-1] > data["Close"].iloc[-2])
                    new_sell_signal = (len(data) > 1 and 
                                      data["Close"].iloc[-1] < data["Open"].iloc[-1] and 
                                      data["Open"].iloc[-1] < data["Close"].iloc[-2])
                    new_pivot_signal = (len(data) > 1 and 
                                       abs(data["Price Change %"].iloc[-1]) > PRICE_CHANGE_THRESHOLD and 
                                       abs(data["Volume Change %"].iloc[-1]) > VOLUME_CHANGE_THRESHOLD)
                    
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

                    continuous_up_buy_signal = data['Continuous_Up'].iloc[-1] >= CONTINUOUS_UP_THRESHOLD
                    continuous_down_sell_signal = data['Continuous_Down'].iloc[-1] >= CONTINUOUS_DOWN_THRESHOLD

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

                    # 显示当前数据
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(f"🟢 股价变动", f"${current_price:.2f}",
                                  f"{price_change:.2f} ({price_pct_change:.2f}%)")
                    with col2:
                        st.metric(f"🔵 成交量变动", f"{last_volume:,}",
                                  f"{volume_change:,} ({volume_pct_change:.2f}%)")

                    # 异动提醒
                    if (abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD) or low_high_signal or high_low_signal or macd_buy_signal or macd_sell_signal or ema_buy_signal or ema_sell_signal or price_trend_buy_signal or price_trend_sell_signal or price_trend_vol_buy_signal or price_trend_vol_sell_signal or price_trend_vol_pct_buy_signal or price_trend_vol_pct_sell_signal or gap_common_up or gap_common_down or gap_breakaway_up or gap_breakaway_down or gap_runaway_up or gap_runaway_down or gap_exhaustion_up or gap_exhaustion_down or continuous_up_buy_signal or continuous_down_sell_signal or sma50_up_trend or sma50_down_trend or sma50_200_up_trend or sma50_200_down_trend or new_buy_signal or new_sell_signal or new_pivot_signal:
                        alert_msg = f"{ticker} 异动：价格 {price_pct_change:.2f}% | 成交量 {volume_pct_change:.2f}%"
                        if low_high_signal:
                            alert_msg += " | Low>High"
                        if high_low_signal:
                            alert_msg += " | High<Low"
                        if macd_buy_signal:
                            alert_msg += " | MACD買入"
                        if macd_sell_signal:
                            alert_msg += " | MACD賣出"
                        if ema_buy_signal:
                            alert_msg += " | EMA買入"
                        if ema_sell_signal:
                            alert_msg += " | EMA賣出"
                        if price_trend_buy_signal:
                            alert_msg += " | 價格趨勢買入"
                        if price_trend_sell_signal:
                            alert_msg += " | 價格趨勢賣出"
                        if price_trend_vol_buy_signal:
                            alert_msg += " | 價格趨勢買入(量)"
                        if price_trend_vol_sell_signal:
                            alert_msg += " | 價格趨勢賣出(量)"
                        if price_trend_vol_pct_buy_signal:
                            alert_msg += " | 價格趨勢買入(量%)"
                        if price_trend_vol_pct_sell_signal:
                            alert_msg += " | 價格趨勢賣出(量%)"
                        if gap_common_up:
                            alert_msg += " | 普通跳空(上)"
                        if gap_common_down:
                            alert_msg += " | 普通跳空(下)"
                        if gap_breakaway_up:
                            alert_msg += " | 突破跳空(上)"
                        if gap_breakaway_down:
                            alert_msg += " | 突破跳空(下)"
                        if gap_runaway_up:
                            alert_msg += " | 持續跳空(上)"
                        if gap_runaway_down:
                            alert_msg += " | 持續跳空(下)"
                        if gap_exhaustion_up:
                            alert_msg += " | 衰竭跳空(上)"
                        if gap_exhaustion_down:
                            alert_msg += " | 衰竭跳空(下)"
                        if continuous_up_buy_signal:
                            alert_msg += f" | 連續向上買入({CONTINUOUS_UP_THRESHOLD})"
                        if continuous_down_sell_signal:
                            alert_msg += f" | 連續向下賣出({CONTINUOUS_DOWN_THRESHOLD})"
                        if sma50_up_trend:
                            alert_msg += " | SMA50上升趨勢"
                        if sma50_down_trend:
                            alert_msg += " | SMA50下降趨勢"
                        if sma50_200_up_trend:
                            alert_msg += " | SMA50_200上升趨勢"
                        if sma50_200_down_trend:
                            alert_msg += " | SMA50_200下降趨勢"
                        if new_buy_signal:
                            alert_msg += " | 新买入信号"
                        if new_sell_signal:
                            alert_msg += " | 新卖出信号"
                        if new_pivot_signal:
                            alert_msg += f" | 新转折点"
                        st.warning(f"📣 {alert_msg}")
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

                    # 成功率
                    st.subheader(f"📊 {ticker} 信号成功率")
                    success_rates = calculate_signal_success_rate(data)
                    success_data = []
                    for signal, metrics in success_rates.items():
                        success_rate = metrics["success_rate"]
                        total_signals = metrics["total_signals"]
                        direction = metrics["direction"]
                        success_data.append({
                            "信号": signal,
                            "成功率 (%)": f"{success_rate:.2f}%",
                            "触发次数": total_signals,
                            "成功定义": "下一交易日收盘价低于当前收盘价" if direction == "down" else "下一交易日收盘价高于当前收盘价"
                        })
                        color = "red" if direction == "down" else "green"
                        st.metric(f"{signal}", f"{success_rate:.2f}%", f"基于 {total_signals} 次 ({'下跌' if direction == 'down' else '上涨'})", delta_color="off")
                        if total_signals > 0 and total_signals < 5:
                            st.warning(f"⚠️ {signal} 样本量过少（{total_signals} 次）")
                    if success_data:
                        st.dataframe(
                            pd.DataFrame(success_data),
                            use_container_width=True,
                            column_config={
                                "信号": st.column_config.TextColumn("信号", width="medium"),
                                "成功率 (%)": st.column_config.TextColumn("成功率 (%)", width="small"),
                                "触发次数": st.column_config.NumberColumn("触发次数", width="small"),
                                "成功定义": st.column_config.TextColumn("成功定义", width="large")
                            }
                        )

                    # K 线图
                    st.subheader(f"📈 {ticker} K线图与技术指标")
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                        subplot_titles=(f"{ticker} K线与EMA", "成交量", "RSI"),
                                        vertical_spacing=0.1, row_heights=[0.5, 0.2, 0.3])
                    fig.add_trace(go.Candlestick(x=data.tail(50)["Datetime"],
                                                open=data.tail(50)["Open"],
                                                high=data.tail(50)["High"],
                                                low=data.tail(50)["Low"],
                                                close=data.tail(50)["Close"],
                                                name="K线"), row=1, col=1)
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
                    
                    fig.update_layout(yaxis_title="价格", yaxis2_title="成交量", yaxis3_title="RSI", showlegend=True, height=600)
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker}_{timestamp}")

                    # 历史数据和数据范围（折叠）
                    with st.expander(f"📋 {ticker} 历史数据与数据范围"):
                        st.subheader("历史数据")
                        display_data = data[["Datetime", "Close", "Volume", "Price Change %", 
                                             "Volume Change %", "異動標記"]].tail(15)
                        if not display_data.empty:
                            st.dataframe(
                                display_data,
                                use_container_width=True,
                                column_config={
                                    "Datetime": st.column_config.DatetimeColumn("时间", format="YYYY-MM-DD HH:mm"),
                                    "Close": st.column_config.NumberColumn("收盘价", format="$%.2f"),
                                    "Volume": st.column_config.NumberColumn("成交量", format="%d"),
                                    "Price Change %": st.column_config.NumberColumn("价格变化 (%)", format="%.2f%"),
                                    "Volume Change %": st.column_config.NumberColumn("成交量变化 (%)", format="%.2f%"),
                                    "異動標記": st.column_config.TextColumn("信号", width="large")
                                }
                            )
                        else:
                            st.warning("⚠️ 无历史数据可显示")

                        st.subheader(f"前 {PERCENTILE_THRESHOLD}% 数据范围")
                        range_data = []
                        for col, label in [("Price Change %", "价格变化 (%)"), 
                                          ("Volume Change %", "成交量变化 (%)"),
                                          ("Volume", "成交量"),
                                          ("📈 股價漲跌幅 (%)", "股价涨跌幅 (%)"),
                                          ("📊 成交量變動幅 (%)", "成交量变动幅 (%)")]:
                            sorted_data = data[col].dropna().sort_values(ascending=False)
                            if len(sorted_data) > 0:
                                top_count = max(1, int(len(sorted_data) * PERCENTILE_THRESHOLD / 100))
                                top_range = sorted_data.head(top_count)
                                range_data.append({
                                    "指标": label,
                                    "范围类型": "最高到最低",
                                    "最大值": f"{top_range.max():,.2f}%",
                                    "最小值": f"{top_range.min():,.2f}%"
                                })
                            sorted_data_asc = data[col].dropna().sort_values(ascending=True)
                            if len(sorted_data_asc) > 0:
                                bottom_count = max(1, int(len(sorted_data_asc) * PERCENTILE_THRESHOLD / 100))
                                bottom_range = sorted_data_asc.head(bottom_count)
                                range_data.append({
                                    "指标": label,
                                    "范围类型": "最低到最高",
                                    "最大值": f"{bottom_range.max():,.2f}%",
                                    "最小值": f"{bottom_range.min():,.2f}%"
                                })
                        if range_data:
                            st.dataframe(
                                pd.DataFrame(range_data),
                                use_container_width=True,
                                column_config={
                                    "指标": st.column_config.TextColumn("指标", width="medium"),
                                    "范围类型": st.column_config.TextColumn("范围类型", width="medium"),
                                    "最大值": st.column_config.TextColumn("最大值", width="small"),
                                    "最小值": st.column_config.TextColumn("最小值", width="small")
                                }
                            )

                        # 下载按钮
                        csv = data.to_csv(index=False)
                        st.download_button(
                            label=f"📥 下载 {ticker} 数据 (CSV)",
                            data=csv,
                            file_name=f"{ticker}_数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                        )

                except Exception as e:
                    st.error(f"⚠️ 无法获取 {ticker} 数据：{e}")

        st.markdown("---")
        st.info(f"📡 页面将在 {REFRESH_INTERVAL} 秒后刷新...")

    time.sleep(REFRESH_INTERVAL)
    placeholder.empty()
