import streamlit as st
import tushare as ts
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from ta import trend, momentum, volume

# ---------------------- 初始化配置 ----------------------
# 替换为你的Tushare Token
ts.set_token("c9502fa704df4f94794b2349dbd0af4f7503931069e03a6aba51fd74")
pro = ts.pro_api()

# 设置页面配置
st.set_page_config(
    page_title="可调整策略选股APP",
    page_icon="📈",
    layout="wide"
)

# ---------------------- 核心函数 ----------------------
@st.cache_data(ttl=3600)  # 缓存数据1小时，避免重复请求
def get_stock_list():
    """获取A股列表（沪深京）"""
    stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,industry,list_date')
    return stock_list

@st.cache_data(ttl=3600)
def get_stock_data(ts_code, start_date, end_date):
    """获取单只股票的历史数据"""
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        # 转换日期格式，按时间排序
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        # 计算常用技术指标
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        # MACD
        macd = trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        # RSI
        df['rsi'] = momentum.RSIIndicator(df['close']).rsi()
        # 成交量均线
        df['vol_ma5'] = df['vol'].rolling(window=5).mean()
        return df
    except Exception as e:
        st.error(f"获取{ts_code}数据失败：{str(e)}")
        return pd.DataFrame()

def select_stocks(strategy_params, stock_list, start_date, end_date):
    """
    核心选股逻辑：根据策略参数筛选股票
    :param strategy_params: 策略参数字典（如均线周期、RSI阈值等）
    :param stock_list: 股票列表
    :param start_date: 开始日期
    :param end_date: 结束日期
    :return: 符合条件的股票列表
    """
    selected_stocks = []
    # 进度条
    progress_bar = st.progress(0)
    total_stocks = len(stock_list)
    
    for idx, row in stock_list.iterrows():
        ts_code = row['ts_code']
        stock_name = row['name']
        industry = row['industry']
        
        # 获取股票数据
        df = get_stock_data(ts_code, start_date, end_date)
        if df.empty or len(df) < 20:  # 数据不足跳过
            progress_bar.progress((idx + 1) / total_stocks)
            continue
        
        # 最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 策略1：均线多头排列 + RSI合理区间
        ma_long = strategy_params['ma_long']
        ma_short = strategy_params['ma_short']
        rsi_min = strategy_params['rsi_min']
        rsi_max = strategy_params['rsi_max']
        
        # 计算对应均线
        ma_short_col = f'ma{ma_short}'
        ma_long_col = f'ma{ma_long}'
        if ma_short_col not in df.columns or ma_long_col not in df.columns:
            progress_bar.progress((idx + 1) / total_stocks)
            continue
        
        # 均线多头：短期均线上穿长期均线，且最新价在均线上方
        ma_condition = (latest[ma_short_col] > latest[ma_long_col]) and (latest['close'] > latest[ma_short_col])
        # RSI在合理区间（避免超买超卖）
        rsi_condition = (rsi_min <= latest['rsi'] <= rsi_max) and not pd.isna(latest['rsi'])
        # MACD金叉（可选）
        macd_condition = (latest['macd_diff'] > 0) and (prev['macd_diff'] <= 0) if strategy_params['use_macd'] else True
        # 成交量放大（可选）
        vol_condition = (latest['vol'] > latest['vol_ma5'] * 1.2) if strategy_params['use_vol'] else True
        
        # 所有条件满足则入选
        if all([ma_condition, rsi_condition, macd_condition, vol_condition]):
            selected_stocks.append({
                '股票代码': row['symbol'],
                '股票名称': stock_name,
                '行业': industry,
                '最新价': latest['close'],
                '涨跌幅': latest['pct_chg'],
                f'{ma_short}日均线': latest[ma_short_col],
                f'{ma_long}日均线': latest[ma_long_col],
                'RSI': round(latest['rsi'], 2),
                'MACD差值': round(latest['macd_diff'], 4),
                '成交量': latest['vol'] / 10000  # 转换为万手
            })
        
        progress_bar.progress((idx + 1) / total_stocks)
    
    progress_bar.empty()
    return pd.DataFrame(selected_stocks)

def plot_stock_chart(ts_code, stock_name, start_date, end_date):
    """绘制股票走势+技术指标图"""
    df = get_stock_data(ts_code, start_date, end_date)
    if df.empty:
        st.warning("暂无数据可绘制")
        return
    
    # 创建子图
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=('股价走势', 'MACD', 'RSI'),
        row_heights=[0.5, 0.25, 0.25]
    )
    
    # 股价+均线
    fig.add_trace(go.Candlestick(
        x=df['trade_date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线'
    ), row=1, col=1)
    fig.add_trace(go.Line(x=df['trade_date'], y=df['ma5'], name='MA5', line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Line(x=df['trade_date'], y=df['ma10'], name='MA10', line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Line(x=df['trade_date'], y=df['ma20'], name='MA20', line=dict(color='green')), row=1, col=1)
    
    # MACD
    fig.add_trace(go.Bar(x=df['trade_date'], y=df['macd_diff'], name='MACD差值'), row=2, col=1)
    fig.add_trace(go.Line(x=df['trade_date'], y=df['macd'], name='MACD', line=dict(color='red')), row=2, col=1)
    fig.add_trace(go.Line(x=df['trade_date'], y=df['macd_signal'], name='信号线', line=dict(color='blue')), row=2, col=1)
    
    # RSI
    fig.add_trace(go.Line(x=df['trade_date'], y=df['rsi'], name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)  # 超买线
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)  # 超卖线
    
    # 布局调整
    fig.update_layout(
        title=f'{stock_name} ({ts_code}) 走势分析',
        height=800,
        showlegend=False,
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------- 页面UI ----------------------
st.title("📈 可调整策略选股APP")
st.divider()

# 侧边栏：策略参数配置
st.sidebar.title("⚙️ 选股策略配置")

# 1. 时间范围选择
st.sidebar.subheader("1. 时间范围")
start_date = st.sidebar.date_input("开始日期", pd.to_datetime("2025-01-01"))
end_date = st.sidebar.date_input("结束日期", pd.to_datetime("2025-12-31"))
start_date_str = start_date.strftime("%Y%m%d")
end_date_str = end_date.strftime("%Y%m%d")

# 2. 均线策略参数
st.sidebar.subheader("2. 均线策略")
ma_short = st.sidebar.slider("短期均线周期", min_value=5, max_value=30, value=10, step=1)
ma_long = st.sidebar.slider("长期均线周期", min_value=20, max_value=60, value=20, step=1)

# 3. RSI参数
st.sidebar.subheader("3. RSI筛选")
rsi_min = st.sidebar.slider("RSI最小值", min_value=0, max_value=50, value=30, step=1)
rsi_max = st.sidebar.slider("RSI最大值", min_value=50, max_value=100, value=70, step=1)

# 4. 可选条件
st.sidebar.subheader("4. 附加条件")
use_macd = st.sidebar.checkbox("启用MACD金叉", value=True)
use_vol = st.sidebar.checkbox("启用成交量放大", value=True)

# 策略参数整合
strategy_params = {
    'ma_short': ma_short,
    'ma_long': ma_long,
    'rsi_min': rsi_min,
    'rsi_max': rsi_max,
    'use_macd': use_macd,
    'use_vol': use_vol
}

# 选股按钮
if st.sidebar.button("🚀 开始选股", type="primary"):
    with st.spinner("正在获取股票列表并筛选..."):
        # 获取股票列表
        stock_list = get_stock_list()
        st.info(f"共获取到 {len(stock_list)} 只A股股票，开始筛选...")
        
        # 执行选股
        selected_df = select_stocks(strategy_params, stock_list, start_date_str, end_date_str)
        st.session_state['selected_df'] = selected_df
        st.session_state['stock_list'] = stock_list  # 保存股票列表，用于查ts_code
        st.session_state['date_range'] = (start_date_str, end_date_str)  # 保存时间范围

if 'selected_df' in st.session_state:
    selected_df = st.session_state['selected_df']
    stock_list = st.session_state['stock_list']
    start_date_str, end_date_str = st.session_state['date_range']
        
        # 展示结果
    st.divider()
    st.subheader(f"✅ 选股结果（共{len(selected_df)}只）")
    if len(selected_df) > 0:
            # 表格展示
         st.dataframe(selected_df, use_container_width=True)
            
            # 下载结果
         csv = selected_df.to_csv(index=False, encoding='utf-8-sig')
         st.download_button(
             label="📥 下载选股结果",
             data=csv,
             file_name=f"选股结果_{start_date_str}_{end_date_str}.csv",
             mime="text/csv"
         )
            
            # 个股分析
         st.divider()
         st.subheader("📊 个股详情分析")
         stock_code = st.selectbox(
         "选择股票查看详情", 
         selected_df['股票代码'].tolist(),
         key="stock_selector"  # 新增key，解决不刷新问题
     )
         stock_info = selected_df[selected_df['股票代码'] == stock_code].iloc[0]
         stock_name = stock_info['股票名称']
            
            # 反向查找ts_code（symbol是6位代码，ts_code是带后缀的）
         ts_code = stock_list[stock_list['symbol'] == stock_code]['ts_code'].iloc[0]
         plot_stock_chart(ts_code, stock_name, start_date_str, end_date_str)
    else:
         st.warning("⚠️ 暂无符合条件的股票，请调整策略参数后重试")

# 说明文档
st.sidebar.divider()
st.sidebar.markdown("""
### 📝 使用说明
1. 替换代码中的Tushare Token
2. 调整策略参数（均线、RSI等）
3. 点击「开始选股」等待结果
4. 可下载结果或查看个股详情

### 🎯 策略逻辑
- 短期均线上穿长期均线（多头）
- RSI在30-70之间（避免超买超卖）
- MACD金叉（可选）
- 成交量放大（可选）
""")