import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import numpy as np

st.set_page_config(page_title="股票技术分析仪表板", layout="wide")

# ------------------------- 安全提取数值 ------------------------- #
def safe_float(val):
    try:
        # DataFrame（如 shape 为 (N,1)）
        if isinstance(val, pd.DataFrame):
            arr = val.values.squeeze()
            return float(arr[-1])
        # Series
        elif isinstance(val, pd.Series):
            return float(val.iloc[-1])
        # ndarray
        elif isinstance(val, np.ndarray):
            return float(val.squeeze()[-1])
        # 其他对象
        elif hasattr(val, "values"):
            return float(val.values[-1])
        elif hasattr(val, "squeeze"):
            return float(val.squeeze())
        else:
            return float(val)
    except Exception as e:
        st.warning(f"⚠️ safe_float 提取失败: {e}")
        return 0.0

# ------------------------- 获取数据并计算指标 ------------------------- #
@st.cache_data(show_spinner=False)
def get_data(ticker, period, interval):
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    data.dropna(inplace=True)
    data = ta.add_all_ta_features(
        data, open="Open", high="High", low="Low",
        close="Close", volume="Volume"
    )
    return data

# ------------------------- 投资建议生成 ------------------------- #
def generate_suggestion(latest, resistance, support):
    close = safe_float(latest["close"])
    rsi = safe_float(latest["momentum_rsi"])
    macd = safe_float(latest["trend_macd"])
    adx = safe_float(latest["trend_adx"])

    suggestion = []
    if rsi > 70:
        suggestion.append("⚠️ RSI 超买，可能出现回调")
    if macd > 0 and adx > 25:
        suggestion.append("✅ MACD 金叉且趋势强，可考虑持有或加仓")
    if close > resistance:
        suggestion.append("🚀 突破阻力位，短期内可能加速上涨")
    if close < support:
        suggestion.append("🔻 跌破支撑位，建议观察风险")

    return "\n".join(suggestion) if suggestion else "当前无显著信号"

# ------------------------- Streamlit 主界面 ------------------------- #
st.sidebar.header("📊 股票参数设置")
ticker = st.sidebar.text_input("股票代码", value="NIO")
period = st.sidebar.selectbox("数据周期 (period)", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"], index=3)
interval = st.sidebar.selectbox("时间粒度 (interval)", ["1m", "5m", "15m", "30m", "1h", "1d", "1wk"], index=5)

# --- 获取数据 ---
try:
    df = get_data(ticker, period, interval)
except Exception as e:
    st.error(f"❌ 数据获取失败: {e}")
    st.stop()

latest = df.iloc[-1]
close_price = safe_float(latest["close"])

st.title(f"{ticker} 技术分析仪表板")
st.caption(f"当前设置：周期 `{period}`，时间间隔 `{interval}`")

# --- 趋势判断 ---
st.subheader("📈 趋势与价格结构")
mean_price = df["close"].mean()
if close_price > mean_price:
    st.success("📈 当前价格高于均值，呈上升趋势")
else:
    st.warning("📉 当前价格低于均值，趋势偏弱")

# --- 技术指标展示 ---
st.subheader("📊 技术指标分析")
cols = st.columns(4)
cols[0].metric("MACD", round(safe_float(latest["trend_macd"]), 3))
cols[1].metric("RSI", round(safe_float(latest["momentum_rsi"]), 2))
cols[2].metric("ADX", round(safe_float(latest["trend_adx"]), 2))
cols[3].metric("CCI", round(safe_float(latest["momentum_cci"]), 2))

# --- 移动平均线展示 ---
st.subheader("📉 移动平均线")
ma5 = df["close"].rolling(window=5).mean().iloc[-1]
ma50 = df["close"].rolling(window=50).mean().iloc[-1]
ma200 = df["close"].rolling(window=200).mean().iloc[-1]
st.write(f"MA5: {ma5:.2f}，MA50: {ma50:.2f}，MA200: {ma200:.2f}")

# --- 支撑与阻力位估算 ---
st.subheader("📌 支撑与阻力区间")
support = df["Low"].tail(20).min()
resistance = df["High"].tail(20).max()
st.write(f"支撑位：${support:.2f}")
st.write(f"阻力位：${resistance:.2f}")

# --- 投资建议输出 ---
st.subheader("🧠 智能投资建议")
advice = generate_suggestion(latest, resistance, support)
st.code(advice)
