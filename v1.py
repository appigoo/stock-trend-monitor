import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from ta.trend import MACD
import datetime

# 📥 抓取 TSLA 數據
st.title("TSLA 股票策略回測")
start_date = st.date_input("選擇開始日期", value=datetime.date.today() - datetime.timedelta(days=90))
end_date = st.date_input("選擇結束日期", value=datetime.date.today())

data = yf.download("TSLA", start=start_date, end=end_date)
data.dropna(inplace=True)

# 🧮 計算 MACD 與成交量移動平均
macd_indicator = MACD(close=data['Close'], window_slow=26, window_fast=12, window_sign=9)
data['MACD'] = macd_indicator.macd()
data['Signal'] = macd_indicator.macd_signal()
data['Volume_MA5'] = data['Volume'].rolling(5).mean()

# 📊 回測參數
initial_cash = 100000
cash = initial_cash
holdings = 0
history = []

# 🧾 回測邏輯
for i in range(1, len(data)):
    today = data.iloc[i]
    yesterday = data.iloc[i - 1]
    conditions_buy = (
        today['High'] > yesterday['High'] and
        today['Low'] > yesterday['Low'] and
        today['Close'] > yesterday['Close'] and
        today['Volume'] > today['Volume_MA5'] and
        today['MACD'] > 0
    )
    conditions_sell = (
        today['High'] < yesterday['High'] and
        today['Low'] < yesterday['Low'] and
        today['Close'] < yesterday['Close'] and
        today['Volume'] > today['Volume_MA5'] and
        today['MACD'] < 0
    )
    date = data.index[i]
    price = today['Close']

    if conditions_buy:
        cost = price * 10
        if cash >= cost:
            cash -= cost
            holdings += 10
            history.append({'Date': date, 'Action': 'Buy', 'Price': price, 'Shares': 10, 'Cash': cash})
    elif conditions_sell and holdings > 0:
        revenue = price * holdings
        cash += revenue
        history.append({'Date': date, 'Action': 'Sell', 'Price': price, 'Shares': holdings, 'Cash': cash})
        holdings = 0

# 💰 結算 & 統計
final_value = cash + holdings * data['Close'].iloc[-1]
total_return = (final_value - initial_cash) / initial_cash * 100
trades = pd.DataFrame(history)
wins = trades[trades['Action'] == 'Sell']
total_trades = len(wins)
avg_profit = wins['Price'].diff().dropna().mean() * 10 if total_trades > 1 else 0
win_rate = (wins['Price'].diff().dropna() > 0).sum() / max(1, total_trades - 1)

# 📈 資金曲線
equity_curve = pd.Series([initial_cash])
running_cash = initial_cash
shares = 0
for row in history:
    if row['Action'] == 'Buy':
        shares += row['Shares']
        running_cash -= row['Price'] * row['Shares']
    elif row['Action'] == 'Sell':
        running_cash += row['Price'] * row['Shares']
        shares -= row['Shares']
    equity_curve = equity_curve.append(pd.Series([running_cash + shares * row['Price']]))

equity_curve.index = [row['Date'] for row in history] + [data.index[-1]]
equity_curve[-1] = final_value

# 📊 顯示結果
st.subheader("📋 回測報告")
st.write(f"總回報率：{total_return:.2f}%")
st.write(f"勝率：{win_rate:.2%}")
st.write(f"平均每筆交易盈虧：{avg_profit:.2f} USD")
st.write(f"總交易次數：{total_trades}")
st.write(f"最後剩餘現金：{cash:.2f} USD")

# 📉 資金曲線圖
st.subheader("📈 資金曲線圖 (Equity Curve)")
fig, ax = plt.subplots()
equity_curve.plot(ax=ax)
ax.set_ylabel("Portfolio Value (USD)")
st.pyplot(fig)

# 🕯️ K 線圖與 MACD
st.subheader("📉 K 線圖含 MACD 與交易訊號")
fig, ax = plt.subplots(2, figsize=(12, 8), sharex=True)

# K 線 + 訊號
ax[0].plot(data.index, data['Close'], label="Close")
for row in history:
    color = 'green' if row['Action'] == 'Buy' else 'red'
    ax[0].scatter(row['Date'], row['Price'], color=color, label=row['Action'], s=50)
ax[0].legend()
ax[0].set_title("TSLA Price + Signals")

# MACD
ax[1].plot(data.index, data['MACD'], label="MACD", color='blue')
ax[1].plot(data.index, data['Signal'], label="Signal", color='orange')
ax[1].legend()
ax[1].set_title("MACD Indicator")
st.pyplot(fig)

# 💾 匯出交易紀錄
st.subheader("📄 交易紀錄 CSV")
csv = trades.to_csv(index=False)
st.download_button("下載交易記錄 CSV", csv, "tsla_trade_history.csv")
