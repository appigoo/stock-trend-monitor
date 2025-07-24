import streamlit as st
import yfinance as yf
import pandas as pd
import ta

st.set_page_config(page_title="NIO 实时分析", layout="wide")

# --- 输入股票代码 ---
ticker = st.sidebar.text_input("输入股票代码", value="NIO")
period = st.sidebar.selectbox("时间区间", ["7d", "1mo", "3mo", "6mo", "1y"], index=2)

# --- 获取数据 ---
data = yf.download(ticker, period=period, interval="1h")
df = data.copy()
df = ta.add_all_ta_features(df, open="Open", high="High", low="Low", close="Close", volume="Volume")

st.title(f"{ticker} 技术分析仪表板")
st.subheader("📈 趋势与价格结构")

# --- 趋势分析 ---
if df["close"].iloc[-1] > df["close"].mean():
    st.success("当前价格高于均值，显示上升趋势迹象 📊")
else:
    st.warning("价格低于均值，趋势疲软 💤")

# --- 技术指标展示 ---
st.subheader("📊 技术指标分析")
latest = df.iloc[-1]
st.metric("MACD", round(latest["trend_macd"], 3))
st.metric("RSI", round(latest["momentum_rsi"], 2))
st.metric("ADX", round(latest["trend_adx"], 2))
st.metric("CCI", round(latest["momentum_cci"], 2))

# --- 移动平均线 ---
st.subheader("📉 移动平均线")
ma5 = df["close"].rolling(window=5).mean().iloc[-1]
ma50 = df["close"].rolling(window=50).mean().iloc[-1]
ma200 = df["close"].rolling(window=200).mean().iloc[-1]
st.write(f"MA5: {ma5:.2f}, MA50: {ma50:.2f}, MA200: {ma200:.2f}")

# --- 支撑阻力逻辑 ---
support = df["Low"].tail(20).min()
resistance = df["High"].tail(20).max()
st.subheader("📌 支撑与阻力位")
st.write(f"支撑位估算：${support:.2f}")
st.write(f"阻力位估算：${resistance:.2f}")

# --- 投资建议输出 ---
st.subheader("🧠 投资建议总结")
suggestion = ""
if latest["momentum_rsi"] > 70:
    suggestion += "⚠️ RSI 超买，可能出现回调\n"
if latest["trend_macd"] > 0 and latest["trend_adx"] > 25:
    suggestion += "✅ MACD 金叉且趋势强，可考虑持有或加仓\n"
if latest["close"] > resistance:
    suggestion += "🚀 突破阻力位，短期内可能加速上涨\n"
if latest["close"] < support:
    suggestion += "🔻 跌破支撑位，建议观察风险\n"

st.code(suggestion if suggestion else "当前无显著信号")

