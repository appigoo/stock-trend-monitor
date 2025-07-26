import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from ta.trend import MACD
import datetime

# 🏁 頁面標題與時間範圍設定
st.title("TSLA 策略回測分析")
start_date = datetime.date.today() - datetime.timedelta(days=90)
end_date = datetime.date.today()

# ⏬ 下載 TSLA 數據
data = yf.download("TSLA", start=start_date, end=end_date)
data.dropna(inplace=True)

# 🧠 計算 MACD、成交量均線
macd_indicator = MACD(close=data['Close'], window_slow=26, window_fast=12, window_sign=9)
data['MACD'] = macd_indicator.macd()
data['Signal'] = macd_indicator.macd_signal()
data['Volume_MA5'] = data['Volume'].rolling(5).mean()

# 💰 回測參數
initial_cash = 100000
cash = initial_cash
holdings = 0
history = []

# 📈 回測邏輯：判斷買入 / 賣出條件
for i in range(1, len(data)):
    today = data.iloc[i]
    yesterday = data.iloc[i - 1]
    date = data.index[i]
    price = today['Close']

    buy_cond = (
        today['High'] > yesterday['High'] and
        today['Low'] > yesterday['Low'] and
        today['Close'] > yesterday['Close'] and
        today['Volume'] > today['Volume_MA5'] and
        today['MACD'] > 0
    )

    sell_cond = (
        today['High'] < yesterday['High'] and
        today['Low'] < yesterday['Low'] and
        today['Close'] < yesterday['Close'] and
        today['Volume'] > today['Volume_MA5'] and
        today['MACD'] < 0
    )

    if buy_cond:
        cost = price * 10
        if cash >= cost:
            cash -= cost
            holdings += 10
            history.append({'Date': date, 'Action': 'Buy', 'Price': price, 'Shares': 10, 'Cash': cash})
    elif sell_cond and holdings > 0:
        revenue = price * holdings
        cash += revenue
        history.append({'Date': date, 'Action': 'Sell', 'Price': price, 'Shares': holdings, 'Cash': cash})
        holdings = 0

# 📋 統計分析
final_value = cash + holdings * data['Close'].iloc[-1]
total_return = (final_value - initial_cash) / initial_cash * 100
trades = pd.DataFrame(history)
sell_trades = trades[trades['Action'] == 'Sell']
trade_count = len(sell_trades)
avg_profit = sell_trades['Price'].diff().dropna().mean() * 10 if trade_count > 1 else 0
win_rate = (sell_trades['Price'].diff().dropna() > 0).sum() / max(1, trade_count - 1)

# 📊 資金曲線建構
running_cash = initial_cash
shares = 0
equity_values = []
equity_index = []

for row in history:
    if row['Action'] == 'Buy':
        shares += row['Shares']
        running_cash -= row['Price'] * row['Shares']
    elif row['Action'] == 'Sell':
        running_cash += row['Price'] * row['Shares']
        shares -= row['Shares']
    equity_values.append(running_cash + shares * row['Price'])
    equity_index.append(row['Date'])

equity_values.append(final_value)
equity_index.append(data.index[-1])
equity_curve = pd.Series(equity_values, index=equity_index)

# 📣 回測報告顯示
st.subheader("📊 回測報告")
st.write(f"總回報率：{total_return:.2f}%")
st.write(f"勝率：{win_rate:.2%}")
st.write(f"平均每筆交易盈虧：{avg_profit:.2f} USD")
st.write(f"總交易次數：{trade_count}")
st.write(f"最後剩餘現金：{cash:.2f} USD")

# 📉 資金曲線圖
st.subheader("📈 資金曲線（Equity Curve）")
fig1, ax1 = plt.subplots()
equity_curve.plot(ax=ax1, color='dodgerblue', linewidth=2)
ax1.set_ylabel("Portfolio Value (USD)")
ax1.set_title("資金隨時間變化曲線")
st.pyplot(fig1)

# 🕯️ K 線圖 + MACD + 交易訊號
st.subheader("📉 K 線圖含 MACD 與交易訊號")
fig2, ax = plt.subplots(2, figsize=(12, 8), sharex=True)

# 收盤價與信號標記
ax[0].plot(data.index, data['Close'], label="Close", color='black')
for row in history:
    color = 'green' if row['Action'] == 'Buy' else 'red'
    ax[0].scatter(row['Date'], row['Price'], color=color, label=row['Action'], s=60)
ax[0].legend()
ax[0].set_title("TSLA 收盤價與交易信號")

# MACD 與訊號線
ax[1].plot(data.index, data['MACD'], label="MACD", color='blue')
ax[1].plot(data.index, data['Signal'], label="Signal", color='orange')
ax[1].legend()
ax[1].set_title("MACD 指標")
st.pyplot(fig2)

# 📁 CSV 匯出交易紀錄
st.subheader("📄 交易紀錄下載 CSV")
csv = trades.to_csv(index=False)
st.download_button("📥 點擊下載交易紀錄", csv, "tsla_trade_history.csv")
