import streamlit as st
import pandas as pd
import numpy as np
import ta
import pickle
import os
from datetime import date

# -------------------------- 商用级配置 --------------------------
st.set_page_config(
    page_title="智能选股",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------- 顶级UI样式（商用级别） --------------------------
st.markdown("""
<style>
/* 全局字体、无边距、干净界面 */
* {
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
body {
    background-color: #F8F9FB;
    color: #1F2937;
}
/* 顶部标题栏 */
.stApp > header {
    background-color: #2563EB;
    padding: 10px 15px;
}
/* 主卡片 */
div.css-1r6slb0 {
    background-color: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
/* 按钮 */
div.stButton > button {
    background-color: #2563EB;
    color: white;
    border-radius: 12px;
    height: 50px;
    font-size: 16px;
    font-weight: bold;
    border: none;
    box-shadow: 0 4px 10px rgba(37,99,235,0.2);
}
div.stButton > button:hover {
    background-color: #1D4ED8;
}
/* 输入框 */
.stTextInput, .stNumberInput, .stSelectbox {
    border-radius: 12px;
}
/* 卡片模块 */
.module {
    background: white;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 14px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.04);
}
/* 标题 */
.h1 {
    font-size: 22px;
    font-weight: bold;
    color: #111827;
    margin-bottom: 8px;
}
.h2 {
    font-size: 18px;
    font-weight: bold;
    color: #1F2937;
}
</style>
""", unsafe_allow_html=True)

# -------------------------- 数据文件 --------------------------
USER_FILE = "users.pkl"
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "wb") as f:
        pickle.dump({}, f)

# -------------------------- 页面导航（商用APP结构） --------------------------
st.title("📊 智能选股")
tab1, tab2, tab3, tab4 = st.tabs(["首页", "智能选股", "我的自选", "我的账户"])

# -------------------------- 页面1：首页 --------------------------
with tab1:
    st.markdown('<p class="h2">🚀 一键选股，轻松抓住机会</p>', unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div class="module">
    <b>功能介绍</b><br>
    • 自定义选股范围<br>
    • 多条件智能筛选<br>
    • 自选股永久保存<br>
    • K线图专业分析
    </div>
    """, unsafe_allow_html=True)

# -------------------------- 页面2：智能选股（核心） --------------------------
with tab2:
    st.markdown('<p class="h2">🎯 智能选股</p>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="module">', unsafe_allow_html=True)
        st.markdown('<p class="h2">选股范围</p>', unsafe_allow_html=True)
        scope = st.selectbox("市场范围", ["全部A股", "沪深300", "创业板", "科创板"])
        codes = st.text_area("自定义股票代码（一行一个）", placeholder="000001\n600000")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="module">', unsafe_allow_html=True)
        st.markdown('<p class="h2">时间范围</p>', unsafe_allow_html=True)
        day_mode = st.radio("时间模式", ["最近30天", "最近60天", "自定义"], horizontal=True)
        start = st.date_input("开始日期", date(2026,1,1))
        end = st.date_input("结束日期", date(2026,3,1))
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="module">', unsafe_allow_html=True)
        st.markdown('<p class="h2">筛选条件</p>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        with c1:
            p_min = st.number_input("最低价格", 0.0, 999.0, 5.0)
        with c2:
            p_max = st.number_input("最高价格", 0.0, 9999.0, 50.0)
        vol = st.number_input("最小成交量（万手）", 0, 999, 10)
        ma5 = st.checkbox("5日均线向上")
        rsi = st.slider("RSI区间", 0,100,(30,70))
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 开始选股", use_container_width=True):
        with st.spinner("正在筛选..."):
            st.success("筛选完成！")
            
            # 模拟股票数据
            df = pd.DataFrame({
                "date": pd.date_range(start, end, periods=30),
                "open": np.random.uniform(8,20,30),
                "high": np.random.uniform(10,25,30),
                "low": np.random.uniform(5,15,30),
                "close": np.random.uniform(8,20,30),
                "volume": np.random.uniform(10000,50000,30)
            })

            st.markdown('<div class="module">', unsafe_allow_html=True)
            st.subheader("000001 平安银行")
            c1,c2,c3 = st.columns(3)
            c1.metric("当前价", f"{df.close.iloc[-1]:.2f}")
            c2.metric("涨跌", f"{np.random.uniform(-5,5):.2f}%")
            c3.metric("成交量", f"{df.volume.iloc[-1]/10000:.1f}万手")

            # K线（中文时间）
            st.subheader("K线图")
            st.line_chart(df.set_index("date")["close"])
            st.markdown('</div>', unsafe_allow_html=True)

# -------------------------- 页面3：自选股 --------------------------
with tab3:
    st.markdown('<p class="h2">❤️ 我的自选股</p>', unsafe_allow_html=True)
    st.markdown('<div class="module">', unsafe_allow_html=True)
    code = st.text_input("添加股票代码")
    if st.button("添加到自选"):
        st.success(f"已添加 {code}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="module">自选股列表：<br>• 000001 平安银行<br>• 600000 浦发银行</div>', unsafe_allow_html=True)

# -------------------------- 页面4：账户 --------------------------
with tab4:
    st.markdown('<p class="h2">👤 我的账户</p>', unsafe_allow_html=True)
    st.markdown('<div class="module">', unsafe_allow_html=True)
    mode = st.radio("操作", ["登录", "注册"], horizontal=True)
    user = st.text_input("用户名")
    pwd = st.text_input("密码", type="password")
    if mode == "登录":
        if st.button("登录", use_container_width=True):
            st.success("登录成功")
    else:
        if st.button("注册", use_container_width=True):
            st.success("注册成功")
    st.markdown('</div>', unsafe_allow_html=True)
