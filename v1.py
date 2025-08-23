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
REFRESH_INTERVAL = 144  # 秒，5 分钟自动刷新
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# 计算信号成功率
def calculate_signal_success_rate(data):
    # 计算下一交易日收盘价是否低于/高于当前收盘价
    data["Next_Close_Lower"] = data["Close"].shift(-1) < data["Close"]
    data["Next_Close_Higher"] = data["Close"].shift(-1) > data["Close"]
    
    # 卖出信号（下一交易日收盘价低于当前）
    sell_signals = [
        "High<Low", "MACD賣出", "EMA賣出", "價格趨勢賣出", "價格趨勢賣出(量)", 
        "價格趨勢賣出(量%)", "普通跳空(下)", "突破跳空(下)", "持續跳空(下)", 
        "衰竭跳空(下)", "連續向下賣出", "SMA50下降趨勢", "SMA50_200下降趨勢", "新卖出信号"
    ]
    
    # 获取所有信号
    all_signals = set()
    for signals in data["異動標記"].dropna():
        for signal in signals.split(", "):
            if signal:
                all_signals.add(signal)
    
    # 计算成功率
    success_rates = {}
    for signal in all_signals:
        signal_rows = data[data["異動標記"].str.contains(signal, na=False)]
        total_signals = len(signal_rows)
        if total_signals == 0:
            success_rates[signal] = {"success_rate": 0.0, "total_signals": 0, "definition": "下一交易日收盘价高于当前" if signal not in sell_signals else "下一交易日收盘价低于当前"}
        else:
            if signal in sell_signals:
                success_count = signal_rows["Next_Close_Lower"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "definition": "下一交易日收盘价低于当前"
                }
            else:
                success_count = signal_rows["Next_Close_Higher"].sum() if not signal_rows.empty else 0
                success_rates[signal] = {
                    "success_rate": (success_count / total_signals) * 100,
                    "total_signals": total_signals,
                    "definition": "下一交易日收盘价高于当前"
                }
    
    return success_rates

# [calculate_macd, calculate_rsi, send_email_alert, mark_signal 函数保持不变，省略以节省空间]

# UI 设定
st.title("📊 股票監控儀表板")
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        input_tickers = st.text_input("股票代號（逗號分隔）", value="TSLA, NIO, TSLL")
        selected_period = st.selectbox("時間範圍", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"], index=2)
        selected_interval = st.selectbox("資料間隔", ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1d", "5d", "1wk", "1mo", "3mo"], index=8)
        PERCENTILE_THRESHOLD = st.selectbox("數據範圍 (%)", [1, 5, 10, 20], index=1)
    with col2:
        PRICE_THRESHOLD = st.number_input("價格異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
        VOLUME_THRESHOLD = st.number_input("成交量異動閾值 (%)", min_value=0.1, max_value=200.0, value=80.0, step=0.1)
        PRICE_CHANGE_THRESHOLD = st.number_input("新转折点 Price Change % 阈值 (%)", min_value=0.1, max_value=200.0, value=5.0, step=0.1)
        VOLUME_CHANGE_THRESHOLD = st.number_input("新转折点 Volume Change % 阈值 (%)", min_value=0.1, max_value=200.0, value=10.0, step=0.1)
        GAP_THRESHOLD = st.number_input("跳空幅度閾值 (%)", min_value=0.1, max_value=50.0, value=1.0, step=0.1)
        CONTINUOUS_UP_THRESHOLD = st.number_input("連續上漲閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)
        CONTINUOUS_DOWN_THRESHOLD = st.number_input("連續下跌閾值 (根K線)", min_value=1, max_value=20, value=3, step=1)

# 排序选项
st.subheader("信号成功率排序")
sort_col, _ = st.columns([2, 3])
with sort_col:
    sort_by = st.selectbox("排序依据", ["成功率 (%)", "触发次数"], index=0)
    sort_order = st.radio("排序顺序", ["降序", "升序"], index=0)

placeholder = st.empty()

while True:
    with placeholder.container():
        st.subheader(f"⏱ 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        selected_tickers = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]

        for ticker in selected_tickers:
            try:
                stock = yf.Ticker(ticker)
                data = stock.history(period=selected_period, interval=selected_interval).reset_index()

                # 检查数据
                if data.empty or len(data) < 2:
                    st.warning(f"⚠️ {ticker} 無數據或數據不足（期間：{selected_period}，間隔：{selected_interval}）")
                    continue
                if "Date" in data.columns:
                    data = data.rename(columns={"Date": "Datetime"})
                elif "Datetime" not in data.columns:
                    st.warning(f"⚠️ {ticker} 數據缺少時間列")
                    continue

                # 计算指标
                data["Price Change %"] = data["Close"].pct_change().round(4) * 100
                data["Volume Change %"] = data["Volume"].pct_change().round(4) * 100
                data["Close_Difference"] = data['Close'].diff().round(2)
                data["前5均價"] = data["Price Change %"].rolling(window=5).mean()
                data["前5均價ABS"] = abs(data["Price Change %"]).rolling(window=5).mean()
                data["前5均量"] = data["Volume"].rolling(window=5).mean()
                data["📈 股價漲跌幅 (%)"] = ((abs(data["Price Change %"]) - data["前5均價ABS"]) / data["前5均價ABS"]).round(4) * 100
                data["📊 成交量變動幅 (%)"] = ((data["Volume"] - data["前5均量"]) / data["前5均量"]).round(4) * 100
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

                # 检测最新信号
                signals = []
                if abs(price_pct_change) >= PRICE_THRESHOLD and abs(volume_pct_change) >= VOLUME_THRESHOLD:
                    signals.append("✅ 量價")
                if len(data) > 1 and data["Low"].iloc[-1] > data["High"].iloc[-2]:
                    signals.append("📈 Low>High")
                if len(data) > 1 and data["High"].iloc[-1] < data["Low"].iloc[-2]:
                    signals.append("📉 High<Low")
                if len(data) > 1 and data["MACD"].iloc[-1] > 0 and data["MACD"].iloc[-2] <= 0:
                    signals.append("📈 MACD買入")
                if len(data) > 1 and data["MACD"].iloc[-1] <= 0 and data["MACD"].iloc[-2] > 0:
                    signals.append("📉 MACD賣出")
                if (len(data) > 1 and data["EMA5"].iloc[-1] > data["EMA10"].iloc[-1] and 
                    data["EMA5"].iloc[-2] <= data["EMA10"].iloc[-2] and 
                    data["Volume"].iloc[-1] > data["Volume"].iloc[-2]):
                    signals.append("📈 EMA買入")
                if (len(data) > 1 and data["EMA5"].iloc[-1] < data["EMA10"].iloc[-1] and 
                    data["EMA5"].iloc[-2] >= data["EMA10"].iloc[-2] and 
                    data["Volume"].iloc[-1] > data["Volume"].iloc[-2]):
                    signals.append("📉 EMA賣出")
                if (len(data) > 1 and data["High"].iloc[-1] > data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] > data["Close"].iloc[-2]):
                    signals.append("📈 價格趨勢買入")
                if (len(data) > 1 and data["High"].iloc[-1] < data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] < data["Close"].iloc[-2]):
                    signals.append("📉 價格趨勢賣出")
                if (len(data) > 1 and data["High"].iloc[-1] > data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] > data["Close"].iloc[-2] and 
                    data["Volume"].iloc[-1] > data["前5均量"].iloc[-1]):
                    signals.append("📈 價格趨勢買入(量)")
                if (len(data) > 1 and data["High"].iloc[-1] < data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] < data["Close"].iloc[-2] and 
                    data["Volume"].iloc[-1] > data["前5均量"].iloc[-1]):
                    signals.append("📉 價格趨勢賣出(量)")
                if (len(data) > 1 and data["High"].iloc[-1] > data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] > data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] > data["Close"].iloc[-2] and 
                    data["Volume Change %"].iloc[-1] > 15):
                    signals.append("📈 價格趨勢買入(量%)")
                if (len(data) > 1 and data["High"].iloc[-1] < data["High"].iloc[-2] and 
                    data["Low"].iloc[-1] < data["Low"].iloc[-2] and 
                    data["Close"].iloc[-1] < data["Close"].iloc[-2] and 
                    data["Volume Change %"].iloc[-1] > 15):
                    signals.append("📉 價格趨勢賣出(量%)")
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
                                signals.append("📈 衰竭跳空(上)")
                            elif is_up_trend and is_high_volume:
                                signals.append("📈 持續跳空(上)")
                            elif data["High"].iloc[-1] > data["High"].iloc[-2:-1].max() and is_high_volume:
                                signals.append("📈 突破跳空(上)")
                            else:
                                signals.append("📈 普通跳空(上)")
                        elif is_down_gap:
                            if is_price_reversal and is_high_volume:
                                signals.append("📉 衰竭跳空(下)")
                            elif is_down_trend and is_high_volume:
                                signals.append("📉 持續跳空(下)")
                            elif data["Low"].iloc[-1] < data["Low"].iloc[-2:-1].min() and is_high_volume:
                                signals.append("📉 突破跳空(下)")
                            else:
                                signals.append("📉 普通跳空(下)")
                if data['Continuous_Up'].iloc[-1] >= CONTINUOUS_UP_THRESHOLD:
                    signals.append("📈 連續向上買入")
                if data['Continuous_Down'].iloc[-1] >= CONTINUOUS_DOWN_THRESHOLD:
                    signals.append("📉 連續向下賣出")
                if pd.notna(data["SMA50"].iloc[-1]):
                    if data["Close"].iloc[-1] > data["SMA50"].iloc[-1]:
                        signals.append("📈 SMA50上升趨勢")
                    elif data["Close"].iloc[-1] < data["SMA50"].iloc[-1]:
                        signals.append("📉 SMA50下降趨勢")
                if pd.notna(data["SMA50"].iloc[-1]) and pd.notna(data["SMA200"].iloc[-1]):
                    if data["Close"].iloc[-1] > data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] > data["SMA200"].iloc[-1]:
                        signals.append("📈 SMA50_200上升趨勢")
                    elif data["Close"].iloc[-1] < data["SMA50"].iloc[-1] and data["SMA50"].iloc[-1] < data["SMA200"].iloc[-1]:
                        signals.append("📉 SMA50_200下降趨勢")
                if len(data) > 1 and data["Close"].iloc[-1] > data["Open"].iloc[-1] and data["Open"].iloc[-1] > data["Close"].iloc[-2]:
                    signals.append("📈 新买入信号")
                if len(data) > 1 and data["Close"].iloc[-1] < data["Open"].iloc[-1] and data["Open"].iloc[-1] < data["Close"].iloc[-2]:
                    signals.append("📉 新卖出信号")
                if len(data) > 1 and abs(data["Price Change %"].iloc[-1]) > PRICE_CHANGE_THRESHOLD and abs(data["Volume Change %"].iloc[-1]) > VOLUME_CHANGE_THRESHOLD:
                    signals.append("🔄 新转折点")

                # 显示当前资料
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(f"{ticker} 🟢 股價變動", f"${current_price:.2f}",
                              f"{price_change:.2f} ({price_pct_change:.2f}%)")
                with col2:
                    st.metric(f"{ticker} 🔵 成交量變動", f"{last_volume:,}",
                              f"{volume_change:,} ({volume_pct_change:.2f}%)")

                # 异动提醒
                if signals:
                    alert_msg = f"{ticker} 異動：價格 {price_pct_change:.2f}%、成交量 {volume_pct_change:.2f}%：{', '.join(signals)}"
                    st.warning(f"📣 {alert_msg}")
                    st.toast(f"📣 {alert_msg}")
                    send_email_alert(ticker, price_pct_change, volume_pct_change, signals)

                # 计算并显示信号成功率
                success_rates = calculate_signal_success_rate(data)
                st.subheader(f"📊 {ticker} 信号成功率")
                success_data = []
                sell_signals_set = set(sell_signals)
                for signal, metrics in success_rates.items():
                    success_rate = metrics["success_rate"]
                    total_signals = metrics["total_signals"]
                    definition = metrics["definition"]
                    success_data.append({
                        "信号": signal,
                        "成功率 (%)": success_rate,
                        "触发次数": total_signals,
                        "定义": definition
                    })
                    if total_signals > 0 and total_signals < 5:
                        st.warning(f"⚠️ {ticker} {signal} 样本量过少（{total_signals} 次），成功率可能不稳定")
                
                if success_data:
                    success_df = pd.DataFrame(success_data)
                    # 按信号类型分组显示（卖出信号红色，其他信号蓝色）
                    success_df["颜色"] = success_df["信号"].apply(lambda x: "red" if x in sell_signals_set else "blue")
                    # 排序
                    sort_key = "成功率 (%)" if sort_by == "成功率 (%)" else "触发次数"
                    success_df = success_df.sort_values(by=sort_key, ascending=(sort_order == "升序"))
                    # 显示表格
                    st.dataframe(
                        success_df[["信号", "成功率 (%)", "触发次数", "定义"]],
                        use_container_width=True,
                        column_config={
                            "信号": st.column_config.TextColumn("信号", width="medium"),
                            "成功率 (%)": st.column_config.NumberColumn("成功率 (%)", format="%.2f%", width="small"),
                            "触发次数": st.column_config.NumberColumn("触发次数", width="small"),
                            "定义": st.column_config.TextColumn("定义", width="medium")
                        }
                    )
                    # 柱状图
                    fig_success = px.bar(
                        success_df,
                        x="信号",
                        y="成功率 (%)",
                        color="颜色",
                        color_discrete_map={"red": "#FF9999", "blue": "#99CCFF"},
                        text="触发次数",
                        title=f"{ticker} 信号成功率（红色为卖出信号，蓝色为其他信号）",
                        height=400
                    )
                    fig_success.update_traces(textposition="auto")
                    fig_success.update_layout(xaxis_title="信号", yaxis_title="成功率 (%)", showlegend=False)
                    st.plotly_chart(fig_success, use_container_width=True)

                # K 线图
                st.subheader(f"📈 {ticker} K線圖與技術指標")
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                    subplot_titles=(f"{ticker} K線與EMA", "成交量", "RSI"),
                                    vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
                
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
                                         text="📈 EMA買入", showarrow=True, arrowhead=2, ax=20, ay=-20, row=1, col=1)
                    elif (data["EMA5"].iloc[idx] < data["EMA10"].iloc[idx] and 
                          data["EMA5"].iloc[idx-1] >= data["EMA10"].iloc[idx-1]):
                        fig.add_annotation(x=data["Datetime"].iloc[idx], y=data["Close"].iloc[idx],
                                         text="📉 EMA賣出", showarrow=True, arrowhead=2, ax=20, ay=20, row=1, col=1)
                    if "关键转折点" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="star", size=10, color="yellow"),
                                       text=[f"🔥 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="关键转折点", row=1, col=1)
                    if "新买入信号" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="triangle-up", size=8, color="green"),
                                       text=[f"📈 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="bottom center", name="新买入信号", row=1, col=1)
                    if "新卖出信号" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="triangle-down", size=8, color="red"),
                                       text=[f"📉 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="新卖出信号", row=1, col=1)
                    if "新转折点" in data["異動標記"].iloc[idx]:
                        fig.add_scatter(x=[data["Datetime"].iloc[idx]], y=[data["Close"].iloc[idx]],
                                       mode="markers+text", marker=dict(symbol="star", size=8, color="purple"),
                                       text=[f"🔄 ${data['Close'].iloc[idx]:.2f}"],
                                       textposition="top center", name="新转折点", row=1, col=1)
                
                fig.update_layout(yaxis_title="價格", yaxis2_title="成交量", yaxis3_title="RSI", showlegend=True, height=600)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{ticker}_{timestamp}")

                # 数据范围表格
                st.subheader(f"📊 {ticker} 前 {PERCENTILE_THRESHOLD}% 數據範圍")
                range_data = []
                for col, name in [("Price Change %", "Price Change %"), 
                                 ("Volume Change %", "Volume Change %"), 
                                 ("Volume", "Volume"), 
                                 ("📈 股價漲跌幅 (%)", "股價漲跌幅 (%)"), 
                                 ("📊 成交量變動幅 (%)", "成交量變動幅 (%)")]:
                    sorted_data = data[col].dropna().sort_values(ascending=False)
                    if len(sorted_data) > 0:
                        top_count = max(1, int(len(sorted_data) * PERCENTILE_THRESHOLD / 100))
                        top_range = sorted_data.head(top_count)
                        range_data.append({
                            "指標": name,
                            "範圍類型": "最高到最低",
                            "最大值": f"{top_range.max():,.2f}%",
                            "最小值": f"{top_range.min():,.2f}%"
                        })
                    sorted_data_asc = data[col].dropna().sort_values(ascending=True)
                    if len(sorted_data_asc) > 0:
                        bottom_count = max(1, int(len(sorted_data_asc) * PERCENTILE_THRESHOLD / 100))
                        bottom_range = sorted_data_asc.head(bottom_count)
                        range_data.append({
                            "指標": name,
                            "範圍類型": "最低到最高",
                            "最大值": f"{bottom_range.max():,.2f}%",
                            "最小值": f"{bottom_range.min():,.2f}%"
                        })
                
                if range_data:
                    st.dataframe(
                        pd.DataFrame(range_data),
                        use_container_width=True,
                        column_config={
                            "指標": st.column_config.TextColumn("指標", width="medium"),
                            "範圍類型": st.column_config.TextColumn("範圍類型", width="medium"),
                            "最大值": st.column_config.TextColumn("最大值", width="small"),
                            "最小值": st.column_config.TextColumn("最小值", width="small")
                        }
                    )

                # 历史数据
                st.subheader(f"📋 歷史資料：{ticker}")
                display_data = data[["Datetime","Low","High", "Close", "Volume", "Price Change %", 
                                     "Volume Change %", "📈 股價漲跌幅 (%)", 
                                     "📊 成交量變動幅 (%)","Close_Difference", "異動標記"]].tail(15)
                if not display_data.empty:
                    st.dataframe(
                        display_data,
                        height=400,
                        use_container_width=True,
                        column_config={
                            "異動標記": st.column_config.TextColumn(width="large")
                        }
                    )

                # 下载按钮
                csv = data.to_csv(index=False)
                st.download_button(
                    label=f"📥 下載 {ticker} 數據 (CSV)",
                    data=csv,
                    file_name=f"{ticker}_數據_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.warning(f"⚠️ 無法取得 {ticker} 的資料：{e}")
                continue

        st.markdown("---")
        st.info("📡 頁面將在 5 分鐘後自動刷新...")

    time.sleep(REFRESH_INTERVAL)
    placeholder.empty()
