# 導入必要的庫
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta

# Streamlit 頁面設置
st.title("股票回測交易策略")
st.write("策略：基於價格、成交量和 MACD 的買入/賣出條件")

# 用戶輸入 Ticker
ticker_input = st.text_input("請輸入股票代碼 (例如：TSLA)", value="TSLA")

# 定義計算 MACD 的函數
def calculate_macd(data, fast=12, slow=26, signal=9):
    """
    計算 MACD 指標
    參數：data (DataFrame) - 包含收盤價的數據
    返回：MACD 線、訊號線、MACD 柱狀圖
    """
    exp1 = data['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

# 獲取股票數據
def get_stock_data(ticker):
    """
    從 yfinance 獲取指定股票近 5 天的 15 分鐘數據
    """
    stock = yf.Ticker(ticker)
    data = stock.history(period="5d", interval="15m")
    data.reset_index(inplace=True)
    return data

# 回測交易策略
def backtest_strategy(data, initial_cash=100000):
    """
    執行回測交易策略
    參數：
        data (DataFrame): 包含 OHLC 和成交量的股票數據
        initial_cash (float): 初始資金
    返回：
        交易記錄、剩餘現金、股權曲線數據、交易訊號
    """
    # 初始化變量
    cash = initial_cash
    position = 0  # 持有股數
    trades = []  # 交易記錄
    equity_curve = []  # 股權曲線
    signals = []  # 買入/賣出訊號

    # 計算前 5 個 15 分鐘 K 線的平均成交量（約 1 小時）
    data['Volume_MA5'] = data['Volume'].rolling(window=5).mean()

    # 計算 MACD
    data['MACD'], data['Signal'], _ = calculate_macd(data)

    for i in range(1, len(data)):
        # 獲取當前和前一 K 線的數據
        today = data.iloc[i]
        yesterday = data.iloc[i-1]

        # 買入條件
        buy_condition = (
            today['High'] > yesterday['High'] and
            today['Low'] > yesterday['Low'] and
            today['Close'] > yesterday['Close'] and
            today['Volume'] > today['Volume_MA5'] and
            today['MACD'] > 0
        )

        # 賣出條件
        sell_condition = (
            today['High'] < yesterday['High'] and
            today['Low'] < yesterday['Low'] and
            today['Close'] < yesterday['Close'] and
            today['Volume'] > today['Volume_MA5'] and
            today['MACD'] < 0
        )

        # 記錄股權曲線
        equity = cash + position * today['Close']
        equity_curve.append({'Date': today['Datetime'], 'Equity': equity})

        # 執行買入
        if buy_condition and position == 0:
            shares_to_buy = 10
            cost = shares_to_buy * today['Close']
            if cash >= cost:
                cash -= cost
                position += shares_to_buy
                trades.append({
                    'Date': today['Datetime'],
                    'Type': 'Buy',
                    'Price': today['Close'],
                    'Shares': shares_to_buy,
                    'Cash': cash,
                    'Equity': equity
                })
                signals.append({'Date': today['Datetime'], 'Signal': 'Buy', 'Price': today['Close']})

        # 執行賣出
        elif sell_condition and position > 0:
            cash += position * today['Close']
            trades.append({
                'Date': today['Datetime'],
                'Type': 'Sell',
                'Price': today['Close'],
                'Shares': position,
                'Cash': cash,
                'Equity': equity
            })
            signals.append({'Date': today['Datetime'], 'Signal': 'Sell', 'Price': today['Close']})
            position = 0

    # 將股權曲線和交易記錄轉為 DataFrame
    equity_df = pd.DataFrame(equity_curve)
    trades_df = pd.DataFrame(trades)
    signals_df = pd.DataFrame(signals)

    return trades_df, cash, equity_df, signals_df

# 計算回測報告
def generate_report(trades_df, initial_cash, final_cash):
    """
    生成回測報告
    """
    total_return = (final_cash - initial_cash) / initial_cash * 100
    total_trades = len(trades_df) // 2  # 每筆交易包含買入和賣出
    if total_trades == 0:
        return {
            '總回報率 (%)': 0,
            '勝率 (%)': 0,
            '平均每筆交易盈虧': 0,
            '總交易次數': 0,
            '最終現金': final_cash
        }

    # 計算勝率和平均每筆交易盈虧
    profits = []
    for i in range(0, len(trades_df)-1, 2):
        buy = trades_df.iloc[i]
        sell = trades_df.iloc[i+1]
        if buy['Type'] == 'Buy' and sell['Type'] == 'Sell':
            profit = (sell['Price'] - buy['Price']) * buy['Shares']
            profits.append(profit)

    win_trades = len([p for p in profits if p > 0])
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
    avg_profit_per_trade = np.mean(profits) if profits else 0

    return {
        '總回報率 (%)': round(total_return, 2),
        '勝率 (%)': round(win_rate, 2),
        '平均每筆交易盈虧': round(avg_profit_per_trade, 2),
        '總交易次數': total_trades,
        '最終現金': round(final_cash, 2)
    }

# 繪製股權曲線
def plot_equity_curve(equity_df):
    """
    繪製股權曲線
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_df['Date'],
        y=equity_df['Equity'],
        mode='lines',
        name='Equity Curve'
    ))
    fig.update_layout(
        title='股權曲線 (Equity Curve)',
        xaxis_title='日期時間',
        yaxis_title='資金 ($)',
        template='plotly_dark'
    )
    return fig

# 繪製 K 線圖和 MACD
def plot_candlestick_with_macd(data, signals_df):
    """
    繪製 K 線圖、MACD 指標和交易訊號
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, 
                        subplot_titles=('K線圖', 'MACD'),
                        row_heights=[0.7, 0.3])

    # K 線圖
    fig.add_trace(go.Candlestick(
        x=data['Datetime'],
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='K線'
    ), row=1, col=1)

    # 添加買入/賣出訊號
    buy_signals = signals_df[signals_df['Signal'] == 'Buy']
    sell_signals = signals_df[signals_df['Signal'] == 'Sell']
    
    fig.add_trace(go.Scatter(
        x=buy_signals['Date'],
        y=buy_signals['Price'],
        mode='markers',
        marker=dict(symbol='triangle-up', size=10, color='green'),
        name='買入訊號'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=sell_signals['Date'],
        y=sell_signals['Price'],
        mode='markers',
        marker=dict(symbol='triangle-down', size=10, color='red'),
        name='賣出訊號'
    ), row=1, col=1)

    # MACD 圖
    fig.add_trace(go.Scatter(
        x=data['Datetime'],
        y=data['MACD'],
        line=dict(color='blue'),
        name='MACD'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=data['Datetime'],
        y=data['Signal'],
        line=dict(color='orange'),
        name='訊號線'
    ), row=2, col=1)

    fig.add_trace(go.Bar(
        x=data['Datetime'],
        y=data['MACD'] - data['Signal'],
        marker=dict(color='grey'),
        name='MACD 柱狀圖'
    ), row=2, col=1)

    fig.update_layout(
        title=f'{ticker_input} K線圖與MACD',
        xaxis_title='日期時間',
        yaxis_title='價格 ($)',
        template='plotly_dark',
        showlegend=True
    )

    return fig

# 主程式
def main():
    # 確保用戶輸入有效的 Ticker
    if not ticker_input:
        st.error("請輸入有效的股票代碼！")
        return

    # 獲取數據
    try:
        data = get_stock_data(ticker_input)
        if data.empty:
            st.error(f"無法獲取 {ticker_input} 的數據，請檢查股票代碼或網絡連接！")
            return
    except Exception as e:
        st.error(f"獲取數據時發生錯誤：{str(e)}")
        return

    # 執行回測
    trades_df, final_cash, equity_df, signals_df = backtest_strategy(data)

    # 生成報告
    report = generate_report(trades_df, initial_cash=100000, final_cash=final_cash)

    # 在 Streamlit 上顯示報告
    st.subheader("回測報告")
    st.write(f"股票代碼: {ticker_input}")
    st.write(f"總回報率: {report['總回報率 (%)']}%")
    st.write(f"勝率: {report['勝率 (%)']}%")
    st.write(f"平均每筆交易盈虧: ${report['平均每筆交易盈虧']}")
    st.write(f"總交易次數: {report['總交易次數']}")
    st.write(f"最終現金: ${report['最終現金']}")

    # 繪製圖表
    st.subheader("股權曲線")
    st.plotly_chart(plot_equity_curve(equity_df))

    st.subheader("K線圖與MACD")
    st.plotly_chart(plot_candlestick_with_macd(data, signals_df))

    # 保存交易記錄為 CSV
    if not trades_df.empty:
        csv_filename = f"{ticker_input}_trades.csv"
        trades_df.to_csv(csv_filename, index=False)
        st.write(f"交易記錄已保存為 '{csv_filename}'")
        st.download_button(
            label="下載交易記錄 CSV",
            data=trades_df.to_csv(index=False),
            file_name=csv_filename,
            mime="text/csv"
        )
    else:
        st.write("無交易記錄生成。")

if __name__ == "__main__":
    main()
