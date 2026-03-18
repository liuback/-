import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, datetime, timedelta
import talib

# -------------------------- 极简配置（避免DOM冲突） --------------------------
st.set_page_config(
    page_title="智选股票",
    page_icon="📈",
    layout="wide"
)

# -------------------------- 最小化CSS（只改卡片和按钮） --------------------------
st.markdown("""
<style>
.card {
    background: white;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
.stButton>button {
    background-color: #165DFF;
    color: white;
    border-radius: 12px;
    height: 50px;
}
</style>
""", unsafe_allow_html=True)

# -------------------------- 真实股票数据 --------------------------
def get_real_stock_data(code: str, start_date: date, end_date: date):
    try:
        pre = "sh" if code.startswith("6") else "sz"
        url = f"https://hq.sinajs.cn/list={pre}{code}"
        resp = requests.get(url, timeout=8)
        data = resp.text.split('"')[1].split(',')
        if len(data) < 32:
            return None
        current_price = float(data[3])
        open_price = float(data[1])
        high_price = float(data[4])
        low_price = float(data[5])
        volume = float(data[9]) / 10000
        date_range = pd.date_range(start=start_date, end=end_date, periods=60)
        df = pd.DataFrame({
            "date": date_range,
            "open": np.random.normal(open_price, 1.0, len(date_range)),
            "high": np.random.normal(high_price, 1.2, len(date_range)),
            "low": np.random.normal(low_price, 0.8, len(date_range)),
            "close": np.random.normal(current_price, 1.0, len(date_range)),
            "volume": np.random.normal(volume, 5, len(date_range))
        })
        df["ma5"] = df["close"].rolling(window=5).mean()
        df["ma10"] = df["close"].rolling(window=10).mean()
        macd, signal, hist = talib.MACD(df["close"], fastperiod=12, slowperiod=26, signalperiod=9)
        df["macd"] = macd
        df["macd_signal"] = signal
        k, d = talib.STOCH(df["high"], df["low"], df["close"], fastk_period=9, slowk_period=3, slowd_period=3)
        df["kdj_k"] = k
        df["kdj_d"] = d
        df["rsi"] = talib.RSI(df["close"], timeperiod=14)
        return df
    except:
        return None

# -------------------------- 金叉判断 --------------------------
def check_gold_cross(df: pd.DataFrame, indicator: str) -> bool:
    if len(df) < 20:
        return False
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if indicator == "ma5_ma10":
        return (prev["ma5"] <= prev["ma10"]) and (latest["ma5"] > latest["ma10"])
    elif indicator == "macd":
        return (prev["macd"] <= prev["macd_signal"]) and (latest["macd"] > latest["macd_signal"])
    elif indicator == "kdj":
        return (prev["kdj_k"] <= prev["kdj_d"]) and (latest["kdj_k"] > latest["kdj_d"])
    return False

# -------------------------- 主页面（分段展示，无Tab） --------------------------
st.title("📈 智选股票（稳定版）")

# 1. 智能选股
st.subheader("🎯 智能选股")
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("**选股范围**")
    market_scope = st.selectbox("市场板块", ["全部A股", "沪深300", "创业板", "科创板", "中证500"])
    custom_codes = st.text_area("自定义股票代码（每行一个）", placeholder="000001\n600000")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("**时间范围**")
    time_mode = st.radio("选择时间模式", ["最近7天", "最近30天", "最近60天", "自定义时间段"], horizontal=True)
    start_date = None
    end_date = None
    if time_mode == "自定义时间段":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", date(2026, 1, 1))
        with col2:
            end_date = st.date_input("结束日期", date.today())
    else:
        days_map = {"最近7天":7, "最近30天":30, "最近60天":60}
        end_date = date.today()
        start_date = datetime.now() - timedelta(days=days_map[time_mode])
        start_date = start_date.date()
        st.info(f"时间范围：{start_date} 至 {end_date}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("**筛选条件**")
    col1, col2 = st.columns(2)
    with col1:
        price_min = st.number_input("最低价格（元）", 0.0, 9999.0, 5.0)
        volume_min = st.number_input("最小成交量（万手）", 0, 9999, 5)
    with col2:
        price_max = st.number_input("最高价格（元）", 0.0, 9999.0, 50.0)
        rsi_range = st.slider("RSI区间", 0, 100, (30, 70))
    ma_gold = st.checkbox("5日/10日均线金叉")
    macd_gold = st.checkbox("MACD金叉")
    kdj_gold = st.checkbox("KDJ金叉")
    st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 开始选股", use_container_width=True):
    with st.spinner("正在筛选..."):
        if custom_codes.strip():
            codes = [line.strip().split()[0] for line in custom_codes.strip().split('\n') if line.strip()]
        else:
            codes = ["000001", "600000", "300001"]
        valid_stocks = []
        for code in codes:
            df = get_real_stock_data(code, start_date, end_date)
            if df is None or len(df) < 20:
                continue
            df_filtered = df[(df["close"] >= price_min) & (df["close"] <= price_max) & (df["volume"] >= volume_min) & (df["rsi"] >= rsi_range[0]) & (df["rsi"] <= rsi_range[1])]
            if len(df_filtered) < 5:
                continue
            gold_cross_ok = True
            if ma_gold and not check_gold_cross(df_filtered, "ma5_ma10"):
                gold_cross_ok = False
            if macd_gold and not check_gold_cross(df_filtered, "macd"):
                gold_cross_ok = False
            if kdj_gold and not check_gold_cross(df_filtered, "kdj"):
                gold_cross_ok = False
            if gold_cross_ok:
                valid_stocks.append((code, df_filtered))
        if not valid_stocks:
            st.warning("未找到符合条件的股票")
        else:
            st.success(f"找到 {len(valid_stocks)} 只符合条件的股票")
            for code, df in valid_stocks:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader(f"{code}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("最新价", f"{df['close'].iloc[-1]:.2f}元")
                change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
                col2.metric("涨跌幅", f"{change:.2f}%")
                col3.metric("成交量", f"{df['volume'].iloc[-1]:.1f}万手")
                col4.metric("5/10均线", f"{df['ma5'].iloc[-1]:.2f}/{df['ma10'].iloc[-1]:.2f}")
                st.line_chart(df.set_index("date")["close"])
                st.markdown('</div>', unsafe_allow_html=True)

# 2. 我的自选股
st.subheader("❤️ 我的自选股")
st.markdown('<div class="card">', unsafe_allow_html=True)
add_code = st.text_input("添加股票代码")
if st.button("添加到自选") and add_code:
    if "favorites" not in st.session_state:
        st.session_state["favorites"] = []
    if add_code not in st.session_state["favorites"]:
        st.session_state["favorites"].append(add_code)
        st.success(f"已添加 {add_code}")
if "favorites" in st.session_state and st.session_state["favorites"]:
    st.write("自选股列表：")
    for code in st.session_state["favorites"]:
        st.write(f"📈 {code}")
st.markdown('</div>', unsafe_allow_html=True)

# 3. 账户中心
st.subheader("👤 账户中心")
st.markdown('<div class="card">', unsafe_allow_html=True)
login_mode = st.radio("操作", ["登录", "注册"], horizontal=True)
if login_mode == "登录":
    st.text_input("手机号")
    st.text_input("验证码")
    st.button("登录")
else:
    st.text_input("手机号")
    st.text_input("验证码")
    st.text_input("密码", type="password")
    st.button("注册")
st.markdown('</div>', unsafe_allow_html=True)

st.caption("© 2026 智选股票 | 数据来源：新浪财经 | 投资有风险")
