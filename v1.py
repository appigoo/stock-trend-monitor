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

# 页面与参数初始化
st.set_page_config(page_title="股票監控儀表板", layout="wide")
load_dotenv()
REFRESH_INTERVAL = 300  # 自动刷新秒数

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# 邮件提醒函数
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

# 用户侧边栏设置参数
st.sidebar.subheader("🔧 提醒參數設定")
PRICE_THRESHOLD = st.sidebar.slider("股價變動門檻 (%)", 0.5, 10.0, 2.0)
VOLUME_THRESHOLD = st.sidebar.slider("成交量變動門檻 (%)", 10.0, 300.0, 50.0)

# 主UI设置
st.title("📊 股票監控儀表板（技術分析 + 策略建議）")
input_tickers = st.text_input("請輸入股票代號（逗號分隔）", value="TSLA, NIO, TSLL")
selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]
period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y"]
interval_options = ["1m", "5m", "15m", "1h", "1d"]
selected_period = st.selectbox("選擇時間範圍", period_options, index=1)
selected_interval = st.selectbox("選擇資料間隔", interval_options, index=1)
window_size = st.slider("滑動平均窗口大小", min_value=2, max_value=40, value=5)

placeholder = st.empty()
if "last_alert_time" not in st.session_state:
    st.session_state["last_alert_time"] = {}

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

                data["異動標記"] = data.apply(
                    lambda row: "✅" if abs(row["Price Change %"]) >= PRICE_THRESHOLD and abs(row["Volume Change %"]) >= VOLUME_THRESHOLD else "", axis=1)

                current_price = data["Close"].iloc[-1]
                previous_close = stock.info.get("previousClose", current_price)
                price_change = current_price - previous_close
                price_pct_change = (price_change / previous_close) * 100 if previous_close else 0

                last_volume = data["Volume"].iloc[-1]
                prev_volume = data["Volume"].iloc[-2] if len(data) > 1 else last_volume
                volume_change = last_volume - prev_volume
                volume_pct_change = (volume_change / prev_volume) * 100 if prev_volume else 0

                st.metric(f"{ticker} 🟢 股價變動", f"${current_price:.2f}", f"{price_change:.2f} ({price_pct_change:.2f}%)")
                st.metric(f"{ticker} 🔵 成交量變動", f"{last_volume:,}", f"{volume_change:,} ({volume_pct_change:.2f}%)")

                now_ts = time.time()
                last_ts = st.session_state["last_alert_time"].get(ticker, 0)
                if now_ts - last_ts > 600:
                    if abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD:
                        send_email_alert(ticker, price_pct_change, volume_pct_change)
                        st.warning(f"📣 {ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%")
                        st.toast(f"📣 {ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%")
                        st.session_state["last_alert_time"][ticker] = now_ts

                st.subheader(f"📋 歷史資料：{ticker}")
                st.dataframe(data[[ "Datetime", "Close", "Price Change %", "📈 股價漲跌幅 (%)", "Volume", "Volume Change %", "📊 成交量變動幅 (%)", "異動標記" ]].tail(10), height=600, use_container_width=True)

                # 📊 技术分析与策略建议
                with st.expander(f"📊 技术分析與投資建議：{ticker}", expanded=True):
                    st.markdown("**📌 技术指标分析**")
                    tech_df = pd.DataFrame({
                        "指标": ["MACD", "RSI (14日)", "Stochastic Oscillator", "ADX (14日)", "CCI (14日)", "ROC (23期)"],
                        "当前值": ["0.115", "69.06", "55.93", "50.49", "169.71", "正值"],
                        "解读": [
                            "底部金叉后持续上扬，动能增强",
                            "接近超买区，但仍属强势区间",
                            "中性偏多，支持上涨趋势",
                            "趋势强度高，表明上涨趋势稳固",
                            "强势买入信号",
                            "价格上涨速度加快"
                        ]
                    })
                    st.dataframe(tech_df, use_container_width=True)

                    st.markdown("**📉 移动平均线趋势分析**")
                    ma_df = pd.DataFrame({
                        "均线周期": ["MA5", "MA50", "MA200"],
                        "当前值": ["4.53", "4.15", "3.67"],
                        "趋势": ["买入信号", "买入信号", "买入信号，长期趋势向好"]
                    })
                    st.dataframe(ma_df, use_container_width=True)

                    st.markdown("**📌 支撑与阻力位**")
                    sr_df = pd.DataFrame({
                        "类型": ["支撑位", "阻力位", "止损位"],
                        "价格区间（美元）": ["4.41 / 3.34", "5.70 / 8.19", "2.98"],
                        "说明": [
                            "若回调至此区间，可考虑加仓",
                            "若突破 $5.70，可能加速上涨",
                            "若跌破此位，建议止损離場"
                        ]
                    })
                    st.dataframe(sr_df, use_container_width=True)

                    st.markdown("**🧭 投资建议总结**")
                    st.markdown("""
                    - 🟢 **短线交易者**：关注 $5.70 的突破机会，若放量突破
