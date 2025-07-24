import streamlit as st
import yfinance as yf
import pandas as pd
import ta

st.set_page_config(page_title="股票技术分析仪表板", layout="wide")

# ------------------------- 模块 1：安全提取数值 ------------------------- #
def safe_float(val):
    try:
        # 如果是 DataFrame 或 ndarray，压缩为一维后取最后一个值
        if isinstance(val, pd.Series) or isinstance(val, pd.DataFrame):
            return float(val.squeeze()[-1])
        elif hasattr(val, "squeeze"):
            return float(val.squeeze())
        elif hasattr(val, "values"):
            return float(val.values[-1])
        else:
            return float(val)
    except Exception as e:
        st.warning(f"⚠️ 指标提取异常: {e}")
        return 0.0

# ------------------------- 模块 2：获取并处理数据 ------------------------- #
@st.cache_data(show_spinner=False)
def get_data(ticker, period, interval):
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    data.dropna(inplace=True)
    data = ta.add_all_ta_features(data,
        open="Open", high="High", low="Low",
        close="Close", volume="Volume"
    )
    return data

# ------------------------- 模块 3：生成投资建议 ------------------------- #
def generate_suggestion(latest, resistance, support):
    suggestion = ""
    close = safe_float(latest["close"])
    rsi = safe_float(latest["momentum_rsi"])
    macd = safe_float(latest["trend_macd"])
    adx = safe_float(latest["trend_adx"])

    if rsi > 70:
        suggestion += "⚠️ RSI 超买，可能出现回调\n"
    if macd > 0 and adx > 25:
        suggestion += "✅ MACD 金叉且趋势强，可考虑持有或加仓\n"
    if close > resistance:
        suggestion += "🚀 突破阻力位，短期内可能加速上涨\n"
    if close < support:
        suggestion += "🔻 跌破支撑位，建议观察风险\n"

    return suggestion if suggestion else "当前无显著信号"

# ------------------------- 模块 4：Streamlit 主界面 ------------------------- #

# --- 侧边栏设置 ---
st.sidebar.header("📊 股票参数")
ticker = st.sidebar.text_input("股票代码", value="NIO")
period = st.sidebar.selectbox("历史数据周期 (period)", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"], index=3)
interval = st.sidebar.selectbox("时间粒度 (interval)", ["1m", "2m", "5m", "15m", "30m", "1h", "1d", "1wk"], index=6)

# --- 获取数据 ---
try:
    df = get_data(ticker, period, interval)
except Exception as e:
    st.error(f"❌ 数据获取失败: {e}")
    st.stop()

latest = df.iloc[-1]
close_price = safe_float(latest["close"])

st.title(f"{ticker} 技术分析仪表板")
st.caption(f"当前选择：周期 `{period}`，时间间隔 `{interval}`")

# --- 趋势判断 ---
st.subheader("📈 趋势与价格结构")
mean_close = df["close"].mean()
if close_price > mean_close:
    st.success("当前价格高于均值，显示上升趋势迹象 📈")
else:
    st.warning("价格低于均值，趋势疲软 💤")

# --- 技术指标展示 ---
st.subheader("📊 技术指标分析")
col1, col2, col3, col4 = st.columns(4)
col1.metric("MACD", round(safe_float(latest["trend_macd"]), 3))
col2.metric("RSI", round(safe_float(latest["momentum_rsi"]), 2))
col3.metric("ADX", round(safe_float(latest["trend_adx"]), 2))
col4.metric("CCI", round(safe_float(latest["momentum_cci"]), 2))

# --- 移动平均线 ---
st.subheader("📉 移动平均线")
ma5 = df["close"].rolling(window=5).mean().iloc[-1]
ma50 = df["close"].rolling(window=50).mean().iloc[-1]
ma200 = df["close"].rolling(window=200).mean().iloc[-1]
st.write(f"MA5: {ma5:.2f}，MA50: {ma50:.2f}，MA200: {ma200:.2f}")

# --- 支撑与阻力位估算 ---
st.subheader("📌 支撑与阻力位")
support = df["Low"].tail(20).min()
resistance = df["High"].tail(20).max()
st.write(f"支撑位估算：${support:.2f}")
st.write(f"阻力位估算：${resistance:.2f}")

# --- 投资建议输出 ---
st.subheader("🧠 投资建议总结")
suggestion = generate_suggestion(latest, resistance, support)
st.code(suggestion)
