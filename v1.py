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
import ta
import traceback

# 页面设置
st.set_page_config(page_title="股票監控儀表板", layout="wide")
load_dotenv()

# 系统参数
REFRESH_INTERVAL = 300
PRICE_THRESHOLD = 2.0
VOLUME_THRESHOLD = 50.0

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# 邮件发送函数
def send_email_alert(ticker, price_pct, volume_pct):
    subject = f"📣 股票異動通知：{ticker}"
    body = f"""
    股票代號：{ticker}
    股價變動：{price_pct:.2f}%
    成交量變動：{volume_pct:.2f}%
    
    系統偵測到價格與成交量同時異常變動，請立即查看市場情況。
    """
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

# 技术指标计算
def apply_technical_indicators(df):
    df = ta.add_all_ta_features(df, open="Open", high="High", low="Low",
                                close="Close", volume="Volume", fillna=True)
    indicators = {
        "MACD": df["momentum_macd"].iloc[-1],
        "RSI (14日)": df["momentum_rsi"].iloc[-1],
        "Stochastic Oscillator": df["momentum_stoch"].iloc[-1],
        "ADX (14日)": df["trend_adx"].iloc[-1],
        "CCI (14日)": df["momentum_cci"].iloc[-1],
        "ROC (23期)": df["momentum_roc"].iloc[-1],
    }
    return indicators

def explain_indicator(name, value):
    if name == "RSI (14日)":
        if value >= 70: return "接近超买区，但仍属强势区间"
        elif value <= 30: return "超卖区，或有反弹机会"
        else: return "中性区域"
    elif name == "ADX (14日)": return "趋势强度高，表明上涨趋势稳固" if value > 40 else "趋势疲软"
    elif name == "CCI (14日)": return "强势买入信号" if value > 100 else "震荡区域"
    elif name == "MACD": return "底部金叉后持续上扬，动能增强" if value > 0 else "动能减弱"
    return "分析中"

def moving_average_trend(df):
    return {
        "MA5": df["Close"].rolling(5).mean().iloc[-1],
        "MA50": df["Close"].rolling(50).mean().iloc[-1],
        "MA200": df["Close"].rolling(200).mean().iloc[-1]
    }

def render_support_resistance():
    st.subheader("📌 支撐與阻力區間")
    st.markdown("""
- 🟢 **支撐位**：$4.41 / $3.34  
- 🔺 **阻力位**：$5.70 / $8.19  
- ⚠️ **止損位**：$2.98  
""")

# 用户输入设置
period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y"]
interval_options = ["1m", "5m", "15m", "1h", "1d"]

st.title("📊 股票監控儀表板（含技術分析與異動提醒 ✅）")
input_tickers = st.text_input("請輸入股票代號（逗號分隔）", value="TSLA, NIO, TSLL")
selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
selected_period = st.selectbox("選擇時間範圍", period_options, index=1)
selected_interval = st.selectbox("選擇資料間隔", interval_options, index=1)
window_size = st.slider("滑動平均窗口大小", min_value=2, max_value=40, value=5)

placeholder = st.empty()

while True:
    with placeholder.container():
        st.subheader(f"⏱ 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for ticker in selected_tickers:
            stock = yf.Ticker(ticker)
            try:
                data = stock.history(period=selected_period, interval=selected_interval).reset_index()
                data["Price Change %"] = data["Close"].pct_change() * 100
                data["Volume Change %"] = data["Volume"].pct_change() * 100
                data["前5均價"] = data["Price Change %"].rolling(window=5).mean()
                data["前5均量"] = data["Volume"].rolling(window=5).mean()
                data["📈 股價漲跌幅 (%)"] = ((data["Price Change %"] - data["前5均價"]) / data["前5均價"]) * 100
                data["📊 成交量變動幅 (%)"] = ((data["Volume"] - data["前5均量"]) / data["前5均量"]) * 100

                def mark_signal(row):
                    if abs(row["Price Change %"]) >= PRICE_THRESHOLD and abs(row["Volume Change %"]) >= VOLUME_THRESHOLD:
                        return "✅"
                    return ""
                data["異動標記"] = data.apply(mark_signal, axis=1)

                current_price = data["Close"].iloc[-1]
                previous_close = stock.info.get("previousClose", current_price)
                price_change = current_price - previous_close
                price_pct_change = (price_change / previous_close) * 100 if previous_close else 0

                last_volume = data["Volume"].iloc[-1]
                prev_volume = data["Volume"].iloc[-2] if len(data) > 1 else last_volume
                volume_change = last_volume - prev_volume
                volume_pct_change = (volume_change / prev_volume) * 100 if prev_volume else 0

                st.metric(f"{ticker} 🟢 股價變動", f"${current_price:.2f}",
                          f"{price_change:.2f} ({price_pct_change:.2f}%)")
                st.metric(f"{ticker} 🔵 成交量變動", f"{last_volume:,}",
                          f"{volume_change:,} ({volume_pct_change:.2f}%)")

                if abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD:
                    alert_msg = f"{ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%"
                    st.warning(f"📣 {alert_msg}")
                    st.toast(f"📣 {alert_msg}")
                    send_email_alert(ticker, price_pct_change, volume_pct_change)

                st.subheader(f"📋 歷史資料：{ticker}")
                st.dataframe(data[[
                    "Datetime", "Close", "Price Change %", "📈 股價漲跌幅 (%)",
                    "Volume", "Volume Change %", "📊 成交量變動幅 (%)", "異動標記"
                ]].tail(10), height=600, use_container_width=True)

                indicators = apply_technical_indicators(data)
                st.subheader(f"📈 技术指标分析：{ticker}")
                for name, value in indicators.items():
                    desc = explain_indicator(name, value)
                    st.metric(label=name, value=f"{value:.2f}", help=desc)

                ma_values = moving_average_trend(data)
                st.subheader(f"📉 均線趨勢：{ticker}")
                for ma_name, ma_val in ma_values.items():
                    signal = "買入信號" if current_price > ma_val else "趨勢下行"
                    st.metric(label=ma_name, value=f"{ma_val:.2f}", help=signal)

                render_support_resistance()

            except Exception as e:
                st.error(f"⚠️ 無法取得 {ticker} 的資料：{e}")
                st.text(traceback.format_exc())

        st.markdown("---")
        st
