import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import numpy as np
import ta
import pickle
import os
import plotly.express as px

# ===================== 安卓移动端适配配置 =====================
st.set_page_config(
    page_title="选股技巧",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 移动端样式优化
st.markdown("""
    <style>
    body {font-size: 16px !important;}
    div.stButton > button {
        width: 100%;
        height: 48px;
        font-size: 18px;
    }
    div.stTextInput > div > div > input {
        height: 48px;
        font-size: 16px;
    }
    @media (max-width: 768px) {
        .element-container {padding: 5px 0 !important;}
    }
    </style>
    """, unsafe_allow_html=True)

# 设置plotly中文显示（核心修复：K线时间中文）
px.defaults.template = "plotly_white"
# 强制设置plotly日期显示为中文
st.markdown("""
<script>
    var config = {
        locale: 'zh-CN'
    };
    Plotly.setPlotConfig(config);
</script>
""", unsafe_allow_html=True)

# ===================== 账户与自选股管理 =====================
USER_DATA_FILE = "user_data.pkl"
def init_user_data():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'wb') as f:
            pickle.dump({}, f)

def user_auth():
    init_user_data()
    with open(USER_DATA_FILE, 'rb') as f:
        user_data = pickle.load(f)
    
    st.sidebar.title("📱 账户管理")
    auth_mode = st.sidebar.radio("选择操作", ["登录", "注册"])
    username = st.sidebar.text_input("用户名")
    password = st.sidebar.text_input("密码", type="password")
    
    if auth_mode == "注册":
        if st.sidebar.button("注册"):
            if username in user_data:
                st.sidebar.error("用户名已存在！")
            else:
                user_data[username] = {"password": password, "favorites": []}
                with open(USER_DATA_FILE, 'wb') as f:
                    pickle.dump(user_data, f)
                st.sidebar.success("注册成功！请登录")
    else:
        if st.sidebar.button("登录"):
            if username not in user_data or user_data[username]["password"] != password:
                st.sidebar.error("用户名/密码错误！")
            else:
                st.session_state["login_user"] = username
                st.session_state["favorites"] = user_data[username]["favorites"]
                st.sidebar.success(f"欢迎 {username}！")

def manage_favorites():
    if "login_user" not in st.session_state:
        st.warning("请先登录账户！")
        return
    
    st.sidebar.divider()
    st.sidebar.title("❤️ 自选股管理")
    
    stock_code = st.sidebar.text_input("添加自选股（代码）")
    if st.sidebar.button("添加") and stock_code:
        if stock_code not in st.session_state["favorites"]:
            st.session_state["favorites"].append(stock_code)
            with open(USER_DATA_FILE, 'rb') as f:
                user_data = pickle.load(f)
            user_data[st.session_state["login_user"]]["favorites"] = st.session_state["favorites"]
            with open(USER_DATA_FILE, 'wb') as f:
                pickle.dump(user_data, f)
            st.sidebar.success(f"已添加 {stock_code} 到自选股！")
    
    if st.session_state["favorites"]:
        st.sidebar.subheader("我的自选股")
        for code in st.session_state["favorites"]:
            col1, col2 = st.sidebar.columns([0.8, 0.2])
            with col1:
                st.write(code)
            with col2:
                if st.button("🗑️", key=code):
                    st.session_state["favorites"].remove(code)
                    with open(USER_DATA_FILE, 'rb') as f:
                        user_data = pickle.load(f)
                    user_data[st.session_state["login_user"]]["favorites"] = st.session_state["favorites"]
                    with open(USER_DATA_FILE, 'wb') as f:
                        pickle.dump(user_data, f)
                    st.experimental_rerun()

# ===================== 自定义选股范围、时间、筛选条件 =====================
def get_stock_list():
    st.sidebar.divider()
    st.sidebar.title("🔍 选股范围")
    
    plate = st.sidebar.selectbox(
        "选择板块",
        ["全部", "沪深300", "创业板", "科创板", "中证500"]
    )
    
    custom_codes = st.sidebar.text_area(
        "自定义股票代码（每行一个）",
        placeholder="例如：\n600000\n000001\n300001"
    )
    
    base_pool = {
        "全部": ["600000", "000001", "300001", "600036", "000858"],
        "沪深300": ["600000", "000001", "600036"],
        "创业板": ["300001", "300750"],
        "科创板": ["688001", "688008"],
        "中证500": ["000858", "002594"]
    }
    
    final_pool = base_pool[plate]
    if custom_codes.strip():
        final_pool = [code.strip() for code in custom_codes.strip().split('\n') if code.strip()]
    
    return final_pool

def get_time_range():
    """核心修复：添加选股时间选择功能"""
    st.sidebar.divider()
    st.sidebar.title("🕒 选股时间范围")
    
    # 时间选择器（适配手机）
    time_type = st.sidebar.radio("时间类型", ["最近N天", "自定义时间段"])
    time_range = {}
    
    if time_type == "最近N天":
        days = st.sidebar.slider("选择天数", min_value=7, max_value=180, value=30, step=7)
        time_range["type"] = "days"
        time_range["value"] = days
    else:
        start_date = st.sidebar.date_input("开始日期", pd.to_datetime("2026-01-01"))
        end_date = st.sidebar.date_input("结束日期", pd.to_datetime("2026-03-01"))
        time_range["type"] = "custom"
        time_range["start"] = start_date
        time_range["end"] = end_date
    
    return time_range

def get_custom_filters():
    st.sidebar.divider()
    st.sidebar.title("🎯 筛选条件")
    
    filters = {}
    filters["price_min"] = st.sidebar.number_input("最低价格", min_value=0.0, value=5.0)
    filters["price_max"] = st.sidebar.number_input("最高价格", min_value=0.0, value=50.0)
    filters["volume_min"] = st.sidebar.number_input("最低成交量（万手）", min_value=0, value=10)
    filters["ma5"] = st.sidebar.checkbox("5日均线向上")
    filters["macd"] = st.sidebar.checkbox("MACD金叉")
    filters["rsi"] = st.sidebar.slider("RSI范围", 0, 100, (30, 70))
    
    return filters

def filter_stocks(stock_data, filters):
    mask = (stock_data["close"] >= filters["price_min"]) & (stock_data["close"] <= filters["price_max"])
    stock_data = stock_data[mask]
    
    mask = stock_data["volume"] >= filters["volume_min"] * 10000
    stock_data = stock_data[mask]
    
    if filters["ma5"]:
        stock_data["ma5"] = stock_data["close"].rolling(window=5).mean()
        mask = stock_data["ma5"].diff() > 0
        stock_data = stock_data[mask]
    
    rsi = ta.momentum.RSIIndicator(stock_data["close"], window=14).rsi()
    mask = (rsi >= filters["rsi"][0]) & (rsi <= filters["rsi"][1])
    stock_data = stock_data[mask]
    
    return stock_data

# ===================== 核心选股逻辑 =====================
def get_stock_data(code, time_range):
    """适配时间选择器，返回对应时间段数据"""
    try:
        # 根据选择的时间范围生成数据
        if time_range["type"] == "days":
            end_date = pd.to_datetime("2026-03-01")
            start_date = end_date - pd.Timedelta(days=time_range["value"])
        else:
            start_date = pd.to_datetime(time_range["start"])
            end_date = pd.to_datetime(time_range["end"])
        
        # 生成对应时间段的日期
        date_range = pd.date_range(start=start_date, end=end_date)
        data = {
            "date": date_range,
            "open": np.random.uniform(10, 20, len(date_range)),
            "high": np.random.uniform(20, 25, len(date_range)),
            "low": np.random.uniform(5, 10, len(date_range)),
            "close": np.random.uniform(10, 20, len(date_range)),
            "volume": np.random.uniform(100000, 500000, len(date_range))
        }
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def plot_stock_chart(df, code):
    """核心修复：K线图时间显示中文"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="K线"
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="成交量"), row=2, col=1)
    
    # 关键：设置x轴日期格式为中文
    fig.update_xaxes(
        tickformat="%Y年%m月%d日",  # 中文日期格式
        tickfont=dict(size=12, family="SimHei"),  # 中文显示字体
        row=1, col=1
    )
    fig.update_xaxes(
        tickformat="%Y年%m月%d日",
        tickfont=dict(size=12, family="SimHei"),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        width=350,
        font=dict(size=14, family="SimHei"),  # 全局中文显示
        margin=dict(l=10, r=10, t=30, b=10),
        title=f"股票{code} K线图",
        title_font=dict(size=16, family="SimHei")
    )
    st.plotly_chart(fig, use_container_width=True)

# ===================== 主函数 =====================
def main():
    st.title("📈 智能选股工具（安卓适配版）")
    
    user_auth()
    if "login_user" in st.session_state:
        manage_favorites()
    
    stock_codes = get_stock_list()
    time_range = get_time_range()  # 新增：获取时间范围
    filters = get_custom_filters()
    
    if st.button("🚀 开始选股", key="select"):
        st.subheader("选股结果")
        for code in stock_codes:
            df = get_stock_data(code, time_range)  # 传入时间范围
            if df.empty:
                continue
            
            filtered_df = filter_stocks(df, filters)
            if filtered_df.empty:
                continue
            
            with st.expander(f"股票代码：{code}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("最新价格", f"{df['close'].iloc[-1]:.2f}")
                with col2:
                    st.metric("涨跌幅", f"{(df['close'].iloc[-1]-df['close'].iloc[-2])/df['close'].iloc[-2]*100:.2f}%")
                
                plot_stock_chart(df, code)

if __name__ == "__main__":
    main()
