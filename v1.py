# 📦 第一步：必要库
import streamlit as st
import yfinance as yf
import pandas as pd
import ta

# 📊 第二步：数据拉取与计算
@st.cache_data
def fetch_data(ticker):
    data = yf.download(ticker, period="3mo", interval="1d")
    data["RSI"] = ta.momentum.rsi(data["Close"])
    macd = ta.trend.macd(data["Close"])
    macd_signal = ta.trend.macd_signal(data["Close"])
    data["MACD_Hist"] = macd - macd_signal
    data["EMA20"] = ta.trend.ema_indicator(data["Close"], window=20)
    data["EMA50"] = ta.trend.ema_indicator(data["Close"], window=50)
    return data

# 📐 第三步：策略评分函数
def strategy_score(rsi, macd_hist, ema_diff, sentiment=0.8, earnings_growth=0.2):
    score = 0
    score += 25 if 30 < rsi < 70 else -10
    score += 25 if macd_hist > 0 else -10
    score += 20 if ema_diff > 0 else -15
    score += 20 * sentiment
    score += 10 * earnings_growth
    return round(score, 2)

def explain_strategy(score):
    if score >= 75:
        return "🔒 建议继续持有：技术面强劲，趋势稳定，长期潜力仍在。"
    elif score >= 50:
        return "🧐 建议观察：部分指标转弱，可能出现震荡，留意止盈位。"
    else:
        return "⚠️ 建议减仓：技术指标恶化，回调风险增大，应考虑部分止盈或保护策略。"

# 🖥️ 第四步：Streamlit 页面布局
st.set_page_config(page_title="TSLA 量化神器", layout="wide")
st.title("🚀 TSLA 智能投资监控面板")

ticker = "TSLA"
data = fetch_data(ticker)
latest = data.iloc[-1]

# 当前持仓信息
st.subheader("📈 当前持仓表现")
entry_price = st.number_input("🔢 成本价 $", value=280.0)
shares = st.number_input("📦 持股数量", value=200)
market_price = round(latest["Close"], 2)
profit = (market_price - entry_price) * shares
st.metric("TSLA 当前价格", f"${market_price}")
st.metric("账面浮盈", f"${profit:,.2f}", delta=f"{(market_price-entry_price)/entry_price:.2%}")

# 技术指标图表
st.subheader("📊 技术指标可视化")
st.line_chart(data[["Close", "EMA20", "EMA50"]])
st.line_chart(data[["RSI", "MACD_Hist"]])

# 策略评分与解释
st.subheader("📋 智能策略建议")
ema_diff = latest["EMA20"] - latest["EMA50"]
score = strategy_score(latest["RSI"], latest["MACD_Hist"], ema_diff)
explanation = explain_strategy(score)
st.metric("策略评分", score)
st.write(explanation)

# 参数控制区
st.subheader("🛠️ 策略参数调节")
sentiment = st.slider("🧠 市场情绪评分", min_value=0.0, max_value=1.0, value=0.8)
earnings_growth = st.slider("💰 盈利增长估计", min_value=-0.5, max_value=0.5, value=0.2)
score = strategy_score(latest["RSI"], latest["MACD_Hist"], ema_diff, sentiment, earnings_growth)
st.success(f"动态评分：{score} ➜ {explain_strategy(score)}")

# 推送建议提示（你可以结合 SMTP 或 Telegram 扩展）
st.info("✅ 可扩展 Email 推送 / Telegram Bot 通知模块，实现实时提醒")

