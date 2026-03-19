# 文件名: stock_selector.py
# 运行方式: streamlit run stock_selector.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta  # 技术指标库
import tushare as ts
import datetime
import pickle
import os
import time
import hashlib
from functools import wraps

# ===================== Tushare 初始化 =====================
# 请在此处填写你的 Tushare token（免费注册：https://tushare.pro）
TS_TOKEN = "c9502fa704df4f94794b2349dbd0af4f7503931069e03a6aba51fd74"  # 替换为实际token
pro = ts.pro_api(TS_TOKEN)

# ===================== 全局变量（用于API频率控制）=====================
LAST_API_CALL = 0

# ===================== 缓存目录设置 =====================
STOCK_CACHE_FILE = "stock_list_cache.pkl"
DAILY_CACHE_DIR = "daily_cache"
if not os.path.exists(DAILY_CACHE_DIR):
    os.makedirs(DAILY_CACHE_DIR)

# ===================== 重试装饰器 =====================
def retry(max_retries=3, delay=2):
    """简单的重试装饰器，用于网络请求"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        print(f"重试 {max_retries} 次后失败: {e}")
                        return None if func.__name__ == 'fetch_daily_data' else []
                    time.sleep(delay)
            return None if func.__name__ == 'fetch_daily_data' else []
        return wrapper
    return decorator

# ===================== 离线备用数据 =====================
OFFLINE_INDUSTRY_BOARDS = [
    {"板块名称": "银行", "板块代码": "BK0475"},
    {"板块名称": "证券", "板块代码": "BK0473"},
    {"板块名称": "保险", "板块代码": "BK0474"},
    {"板块名称": "石油行业", "板块代码": "BK0464"},
    {"板块名称": "煤炭行业", "板块代码": "BK0437"},
    {"板块名称": "有色金属", "板块代码": "BK0478"},
    {"板块名称": "钢铁行业", "板块代码": "BK0479"},
    {"板块名称": "电力行业", "板块代码": "BK0428"},
    {"板块名称": "汽车行业", "板块代码": "BK0481"},
    {"板块名称": "家电行业", "板块代码": "BK0456"},
    {"板块名称": "酿酒行业", "板块代码": "BK0477"},
    {"板块名称": "食品饮料", "板块代码": "BK0438"},
    {"板块名称": "医药制造", "板块代码": "BK0465"},
    {"板块名称": "半导体", "板块代码": "BK0917"},
    {"板块名称": "软件服务", "板块代码": "BK0737"},
    {"板块名称": "互联网服务", "板块代码": "BK0447"},
    {"板块名称": "计算机设备", "板块代码": "BK0448"},
    {"板块名称": "通信设备", "板块代码": "BK0449"},
    {"板块名称": "电子元件", "板块代码": "BK0459"},
]

OFFLINE_CONCEPT_BOARDS = [
    {"板块名称": "人工智能", "板块代码": "BK0809"},
    {"板块名称": "大数据", "板块代码": "BK0634"},
    {"板块名称": "云计算", "板块代码": "BK0705"},
    {"板块名称": "区块链", "板块代码": "BK0830"},
    {"板块名称": "国产芯片", "板块代码": "BK0891"},
    {"板块名称": "军工", "板块代码": "BK0490"},
    {"板块名称": "新能源", "板块代码": "BK0493"},
    {"板块名称": "新能源车", "板块代码": "BK0900"},
    {"板块名称": "光伏", "板块代码": "BK0828"},
    {"板块名称": "风能", "板块代码": "BK0595"},
    {"板块名称": "锂电池", "板块代码": "BK0574"},
    {"板块名称": "5G概念", "板块代码": "BK0714"},
    {"板块名称": "物联网", "板块代码": "BK0734"},
    {"板块名称": "虚拟现实", "板块代码": "BK0722"},
    {"板块名称": "生物疫苗", "板块代码": "BK0832"},
]

OFFLINE_BOARD_STOCKS = {
    "银行": ["000001", "600000", "600036", "601166", "601288", "601328", "601398", "601939", "601988"],
    "证券": ["600030", "600837", "601688", "601211", "601788", "002736", "000776", "000783"],
    "保险": ["601318", "601628", "601601", "601336"],
    "石油行业": ["600028", "601857", "600256", "002221"],
    "煤炭行业": ["601088", "600188", "601225", "600348"],
    "有色金属": ["601600", "600547", "600489", "000878"],
    "钢铁行业": ["600019", "000709", "002075", "600010"],
    "电力行业": ["600900", "600011", "600027", "601985"],
    "汽车行业": ["002594", "600104", "000625", "601633"],
    "家电行业": ["000333", "600690", "000651", "002032"],
    "酿酒行业": ["600519", "000858", "000568", "600809"],
    "食品饮料": ["600887", "603288", "002304", "600873"],
    "医药制造": ["600276", "000538", "300760", "002007"],
    "半导体": ["688981", "603986", "600703", "002049", "300661"],
    "软件服务": ["600570", "300033", "002230", "300454"],
    "互联网服务": ["300059", "002410", "300418", "300113"],
    "计算机设备": ["000977", "603019", "300308", "002415"],
    "通信设备": ["000063", "600498", "300628", "300502"],
    "电子元件": ["002475", "300433", "600183", "002600"],
    "人工智能": ["002230", "300418", "300308", "300454", "688111"],
    "大数据": ["300166", "300229", "002439", "300212"],
    "云计算": ["300383", "300017", "600588", "300253"],
    "区块链": ["300468", "300542", "002195", "300663"],
    "国产芯片": ["002049", "603986", "300474", "300672"],
    "军工": ["600893", "000768", "002179", "300114"],
    "新能源": ["300750", "002129", "002074", "300274"],
    "新能源车": ["002594", "300750", "002460", "002466"],
    "光伏": ["601012", "300274", "002129", "600438"],
    "风能": ["002202", "300129", "600416", "601615"],
    "锂电池": ["300750", "002460", "002466", "300073"],
    "5G概念": ["000063", "300628", "300502", "002475"],
    "物联网": ["300007", "300349", "300075", "300066"],
    "虚拟现实": ["300081", "300113", "300264", "300496"],
    "生物疫苗": ["300601", "300122", "300142", "300238"],
}

# ===================== 页面配置 =====================
st.set_page_config(
    page_title="智能选股工具",
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

# ===================== 辅助函数：转换股票代码格式 =====================
def convert_code_to_tushare(code):
    """
    将6位数字股票代码转换为 Tushare 格式（带后缀）
    规则：6开头 -> .SH，0/3开头 -> .SZ，4/8开头 -> .BJ
    如果代码已经带后缀，则直接返回
    """
    code = code.strip().upper()
    if '.' in code:
        return code  # 已经带后缀
    if code.startswith('6'):
        return code + '.SH'
    elif code.startswith(('0', '3')):
        return code + '.SZ'
    elif code.startswith(('4', '8')):
        return code + '.BJ'
    else:
        return code

# ===================== 数据缓存函数 =====================
@st.cache_data(ttl=3600)
def fetch_stock_list(force_refresh=False):
    """
    获取所有股票代码列表，优先使用本地缓存，每小时最多请求一次API
    force_refresh: 强制从网络更新缓存
    """
    global LAST_API_CALL
    
    # 1. 如果强制刷新且距离上次调用超过1小时，尝试从网络获取
    current_time = time.time()
    if force_refresh and (current_time - LAST_API_CALL > 3600):
        try:
            df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name')
            if df is not None and not df.empty:
                # 保存到本地缓存文件
                with open(STOCK_CACHE_FILE, 'wb') as f:
                    pickle.dump(df[['symbol', 'name']].rename(columns={'symbol': 'code'}), f)
                LAST_API_CALL = current_time
                st.success("已从网络更新股票列表并缓存")
                return df[['symbol', 'name']].rename(columns={'symbol': 'code'})
        except Exception as e:
            st.warning(f"网络获取失败: {e}，尝试读取本地缓存")
    
    # 2. 尝试读取本地缓存文件
    if os.path.exists(STOCK_CACHE_FILE):
        try:
            with open(STOCK_CACHE_FILE, 'rb') as f:
                df = pickle.load(f)
                st.info(f"使用本地缓存的股票列表（{len(df)}只）")
                return df
        except Exception as e:
            st.warning(f"读取缓存失败: {e}")
    
    # 3. 最后回退到离线数据
    st.warning("使用离线股票数据（可能不完整）")
    return pd.DataFrame({
        "code": ["000001", "600000", "300001", "000858", "002594"],
        "name": ["平安银行", "浦发银行", "特锐德", "五粮液", "比亚迪"]
    })

def get_cache_path(symbol, start_date, end_date):
    """生成日线数据缓存文件路径（基于参数哈希）"""
    param_str = f"{symbol}_{start_date}_{end_date}"
    hash_str = hashlib.md5(param_str.encode()).hexdigest()
    return os.path.join(DAILY_CACHE_DIR, f"{hash_str}.pkl")

@st.cache_data(ttl=300)
@retry(max_retries=3, delay=3)
def fetch_daily_data(symbol, start_date, end_date):
    """
    获取股票日线数据，优先读取本地缓存，再请求网络
    """
    cache_path = get_cache_path(symbol, start_date, end_date)
    
    # 1. 检查缓存是否存在且在有效期内（7天内）
    if os.path.exists(cache_path):
        file_time = os.path.getmtime(cache_path)
        if time.time() - file_time < 7 * 24 * 3600:  # 7天有效
            try:
                with open(cache_path, 'rb') as f:
                    df = pickle.load(f)
                    st.caption(f"使用缓存数据: {symbol}")
                    return df
            except:
                pass  # 读取失败则重新获取
    
    # 2. 控制API调用频率（避免超过限制）
    global LAST_API_CALL
    current_time = time.time()
    if current_time - LAST_API_CALL < 0.5:  # 至少间隔0.5秒
        time.sleep(0.5 - (current_time - LAST_API_CALL))
    
    # 3. 请求网络
    try:
        ts_code = convert_code_to_tushare(symbol)
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        LAST_API_CALL = time.time()
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        df = df.sort_values('trade_date')
        df.rename(columns={
            "trade_date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "vol": "volume",
            "amount": "amount",
            "pct_chg": "pct_change"
        }, inplace=True)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        
        # 保存到缓存
        with open(cache_path, 'wb') as f:
            pickle.dump(df, f)
        
        return df
    except Exception as e:
        st.warning(f"获取 {symbol} 数据失败: {e}")
        raise e

# ===================== 技术指标添加 =====================
def add_technical_indicators(df):
    """添加常用技术指标"""
    if df.empty or len(df) < 20:
        return df
    
    df["ma5"] = ta.trend.sma_indicator(df["close"], window=5)
    df["ma10"] = ta.trend.sma_indicator(df["close"], window=10)
    df["ma20"] = ta.trend.sma_indicator(df["close"], window=20)
    df["ma60"] = ta.trend.sma_indicator(df["close"], window=60)
    
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"] = macd.macd_diff()
    
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    
    kdj = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=14)
    df["kdj_k"] = kdj.stoch()
    df["kdj_d"] = kdj.stoch_signal()
    
    bollinger = ta.volatility.BollingerBands(df["close"], window=20)
    df["bollinger_high"] = bollinger.bollinger_hband()
    df["bollinger_low"] = bollinger.bollinger_lband()
    df["bollinger_mid"] = bollinger.bollinger_mavg()
    
    df["volume_ma5"] = df["volume"].rolling(5).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma5"]
    
    return df

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
    
    with st.sidebar:
        st.title("👤 账户管理")
        auth_mode = st.radio("选择操作", ["登录", "注册"], horizontal=True)
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        
        if auth_mode == "注册":
            if st.button("注册"):
                if username in user_data:
                    st.error("用户名已存在！")
                else:
                    user_data[username] = {"password": password, "favorites": []}
                    with open(USER_DATA_FILE, 'wb') as f:
                        pickle.dump(user_data, f)
                    st.success("注册成功！请登录")
        else:
            if st.button("登录"):
                if username not in user_data or user_data[username]["password"] != password:
                    st.error("用户名/密码错误！")
                else:
                    st.session_state["login_user"] = username
                    st.session_state["favorites"] = user_data[username]["favorites"]
                    st.success(f"欢迎 {username}！")
                    st.rerun()

def manage_favorites():
    if "login_user" not in st.session_state:
        return
    
    with st.sidebar:
        st.divider()
        st.title("❤️ 自选股管理")
        stock_code = st.text_input("添加自选股（代码）")
        if st.button("添加") and stock_code:
            code = stock_code.strip()
            if code not in st.session_state["favorites"]:
                st.session_state["favorites"].append(code)
                with open(USER_DATA_FILE, 'rb') as f:
                    user_data = pickle.load(f)
                user_data[st.session_state["login_user"]]["favorites"] = st.session_state["favorites"]
                with open(USER_DATA_FILE, 'wb') as f:
                    pickle.dump(user_data, f)
                st.success(f"已添加 {code} 到自选股！")
        
        if st.session_state["favorites"]:
            st.subheader("我的自选股")
            for code in st.session_state["favorites"]:
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.write(code)
                with col2:
                    if st.button("🗑️", key=f"del_{code}"):
                        st.session_state["favorites"].remove(code)
                        with open(USER_DATA_FILE, 'rb') as f:
                            user_data = pickle.load(f)
                        user_data[st.session_state["login_user"]]["favorites"] = st.session_state["favorites"]
                        with open(USER_DATA_FILE, 'wb') as f:
                            pickle.dump(user_data, f)
                        st.rerun()

# ===================== 自定义板块搜索（使用离线数据）=====================
def fetch_industry_boards():
    """获取所有行业板块列表，使用离线数据"""
    return OFFLINE_INDUSTRY_BOARDS

def fetch_concept_boards():
    """获取所有概念板块列表，使用离线数据"""
    return OFFLINE_CONCEPT_BOARDS

def fetch_board_stocks(board_name, board_code, board_type):
    """获取板块成分股，使用离线数据"""
    return OFFLINE_BOARD_STOCKS.get(board_name, [])

def search_custom_boards():
    with st.sidebar:
        st.divider()
        st.title("🔎 自定义板块搜索")
        st.caption("输入板块关键词，如：银行、石油、半导体、人工智能")
        
        search_keywords = st.text_input(
            "关键词（多个用空格分隔）",
            placeholder="例如：银行 证券 保险"
        )
        
        if st.button("搜索板块", use_container_width=True, key="search_board_btn"):
            if not search_keywords.strip():
                st.warning("请输入关键词")
                return []
            
            keywords = [k.strip() for k in search_keywords.split() if k.strip()]
            
            with st.spinner("正在搜索板块..."):
                industry_boards = fetch_industry_boards()
                concept_boards = fetch_concept_boards()
                
                matched_boards = []
                
                for board in industry_boards:
                    name = board['板块名称']
                    for keyword in keywords:
                        if keyword in name:
                            matched_boards.append({
                                '名称': name,
                                '代码': board['板块代码'],
                                '类型': '行业板块'
                            })
                            break
                
                for board in concept_boards:
                    name = board['板块名称']
                    for keyword in keywords:
                        if keyword in name:
                            matched_boards.append({
                                '名称': name,
                                '代码': board['板块代码'],
                                '类型': '概念板块'
                            })
                            break
                
                unique_boards = []
                seen_names = set()
                for board in matched_boards:
                    if board['名称'] not in seen_names:
                        seen_names.add(board['名称'])
                        unique_boards.append(board)
                
                if not unique_boards:
                    st.warning(f"未找到包含关键词「{search_keywords}」的板块")
                    return []
                
                # 自动选择唯一板块
                if len(unique_boards) == 1:
                    board = unique_boards[0]
                    with st.spinner(f"正在获取 {board['名称']} 成分股..."):
                        stocks = fetch_board_stocks(board['名称'], board['代码'], 
                                                   'industry' if board['类型']=='行业板块' else 'concept')
                        if stocks:
                            st.success(f"成功获取 {len(stocks)} 只股票")
                            st.session_state["custom_board_stocks"] = stocks
                            st.session_state["custom_board_source"] = f"板块搜索: {search_keywords}"
                            st.rerun()
                        else:
                            st.error(f"获取 {board['名称']} 成分股失败")
                    return
                
                st.success(f"找到 {len(unique_boards)} 个相关板块")
                st.subheader("请选择要包含的板块")
                selected_names = []
                for board in unique_boards:
                    if st.checkbox(f"{board['名称']} ({board['类型']})", key=f"board_{board['代码']}"):
                        selected_names.append(board)
                
                if selected_names and st.button("确认选择", key="confirm_boards"):
                    all_stocks = []
                    failed_boards = []
                    progress_text = st.empty()
                    
                    for i, board in enumerate(selected_names):
                        progress_text.text(f"正在获取 {board['名称']} 成分股... ({i+1}/{len(selected_names)})")
                        stocks = fetch_board_stocks(board['名称'], board['代码'], 
                                                   'industry' if board['类型']=='行业板块' else 'concept')
                        if stocks:
                            all_stocks.extend(stocks)
                        else:
                            failed_boards.append(board['名称'])
                        time.sleep(0.5)
                    
                    all_stocks = list(set(all_stocks))
                    progress_text.empty()
                    
                    if failed_boards:
                        st.warning(f"以下板块获取失败: {', '.join(failed_boards)}")
                    
                    if all_stocks:
                        st.success(f"成功获取 {len(all_stocks)} 只股票")
                        st.session_state["custom_board_stocks"] = all_stocks
                        st.session_state["custom_board_source"] = f"板块搜索: {search_keywords}"
                        st.rerun()
                    else:
                        st.error("未获取到任何股票")
        
        if "custom_board_stocks" in st.session_state and st.session_state["custom_board_stocks"]:
            st.info(f"当前自定义板块: {st.session_state.get('custom_board_source', '')}\n股票数量: {len(st.session_state['custom_board_stocks'])} 只")
            if st.button("清除自定义板块", key="clear_boards"):
                st.session_state["custom_board_stocks"] = []
                st.session_state["custom_board_source"] = ""
                st.rerun()
    
    return []

# ===================== 选股范围与筛选条件 =====================
def select_stock_pool():
    with st.sidebar:
        st.divider()
        st.title("📋 选股范围")
        
        # 刷新按钮和板块选择
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            plate = st.selectbox(
                "选择板块",
                ["全部A股", "沪深300成分股", "创业板", "科创板", "自定义代码", "自定义板块搜索"]
            )
        with col2:
            if st.button("🔄 刷新列表", help="手动从Tushare更新股票列表"):
                with st.spinner("正在更新股票列表..."):
                    fetch_stock_list.clear()  # 清除Streamlit缓存
                    fetch_stock_list(force_refresh=True)
                    st.rerun()
        
        if plate == "自定义板块搜索":
            search_custom_boards()
            if "custom_board_stocks" in st.session_state and st.session_state["custom_board_stocks"]:
                codes = st.session_state["custom_board_stocks"]
                source_info = st.session_state.get("custom_board_source", "自定义板块")
                st.caption(f"当前使用: {source_info}")
            else:
                codes = []
                st.info("请在上方搜索板块并选择")
        elif plate == "自定义代码":
            custom_codes = st.text_area(
                "每行一个股票代码",
                placeholder="例如：\n000001\n600000\n300001"
            )
            if custom_codes.strip():
                codes = [line.strip() for line in custom_codes.strip().split("\n") if line.strip()]
            else:
                codes = []
        else:
            stock_list = fetch_stock_list()
            if plate == "全部A股":
                codes = stock_list["code"].tolist()
            elif plate == "沪深300成分股":
                # 简化处理，返回部分股票
                codes = stock_list["code"].tolist()[:300]
            elif plate == "创业板":
                codes = [c for c in stock_list["code"] if c.startswith("30")]
            elif plate == "科创板":
                codes = [c for c in stock_list["code"] if c.startswith("68")]
            else:
                codes = []
        
        # 滑块控制数量
        if codes:
            if len(codes) == 1:
                selected_codes = codes
                st.caption(f"只有 1 只股票")
            else:
                max_stocks = st.slider(
                    "最多处理股票数量", 
                    min_value=1, 
                    max_value=len(codes), 
                    value=min(100, len(codes)),
                    step=1
                )
                selected_codes = codes[:max_stocks]
                st.caption(f"将处理前 {max_stocks} 只股票（共 {len(codes)} 只）")
        else:
            selected_codes = []
            st.caption("当前范围无股票")
        
        st.session_state["stock_pool"] = selected_codes

def select_time_range():
    with st.sidebar:
        st.divider()
        st.title("⏰ 时间范围")
        col1, col2 = st.columns(2)
        today = datetime.date.today()
        default_start = today - datetime.timedelta(days=365)
        with col1:
            start_date = st.date_input(
                "开始日期",
                value=default_start,
                min_value=datetime.date(2000, 1, 1),
                max_value=today
            )
        with col2:
            end_date = st.date_input(
                "结束日期",
                value=today,
                min_value=start_date,
                max_value=today
            )
        st.session_state["start_date"] = start_date.strftime("%Y%m%d")
        st.session_state["end_date"] = end_date.strftime("%Y%m%d")
        st.caption(f"数据区间：{start_date} 至 {end_date}")

def get_filter_conditions():
    with st.sidebar:
        st.divider()
        st.title("🔧 筛选条件")
        
        filters = {}
        
        col1, col2 = st.columns(2)
        with col1:
            filters["price_min"] = st.number_input("最低价", min_value=0.0, value=0.0, step=0.1)
        with col2:
            filters["price_max"] = st.number_input("最高价", min_value=0.0, value=1000.0, step=0.1)
        
        filters["volume_min"] = st.number_input("最低成交量(万股)", min_value=0, value=0, step=10)
        
        st.subheader("技术指标")
        filters["ma5_direction"] = st.selectbox("5日均线方向", ["无", "向上", "向下"])
        filters["ma10_direction"] = st.selectbox("10日均线方向", ["无", "向上", "向下"])
        filters["ma20_direction"] = st.selectbox("20日均线方向", ["无", "向上", "向下"])
        filters["macd_cross"] = st.selectbox("MACD", ["无", "金叉", "死叉"])
        rsi_range = st.slider("RSI范围", 0, 100, (0, 100))
        filters["rsi_min"], filters["rsi_max"] = rsi_range
        filters["kdj_cross"] = st.selectbox("KDJ", ["无", "K线上穿D线", "K线下穿D线"])
        filters["bollinger"] = st.selectbox("布林带位置", ["无", "突破上轨", "跌破下轨", "中轨附近"])
        
        return filters

def apply_filters(df, filters):
    if df.empty or len(df) < 20:
        return False
    
    latest = df.iloc[-1]
    
    if not (filters["price_min"] <= latest["close"] <= filters["price_max"]):
        return False
    if latest["volume"] / 10000 < filters["volume_min"]:
        return False
    
    if filters["ma5_direction"] == "向上" and df["ma5"].diff().iloc[-1] <= 0:
        return False
    if filters["ma5_direction"] == "向下" and df["ma5"].diff().iloc[-1] >= 0:
        return False
    if filters["ma10_direction"] == "向上" and df["ma10"].diff().iloc[-1] <= 0:
        return False
    if filters["ma10_direction"] == "向下" and df["ma10"].diff().iloc[-1] >= 0:
        return False
    if filters["ma20_direction"] == "向上" and df["ma20"].diff().iloc[-1] <= 0:
        return False
    if filters["ma20_direction"] == "向下" and df["ma20"].diff().iloc[-1] >= 0:
        return False
    
    if filters["macd_cross"] == "金叉":
        if df["macd"].iloc[-1] <= df["macd_signal"].iloc[-1] or df["macd"].iloc[-2] <= df["macd_signal"].iloc[-2]:
            return False
    if filters["macd_cross"] == "死叉":
        if df["macd"].iloc[-1] >= df["macd_signal"].iloc[-1] or df["macd"].iloc[-2] >= df["macd_signal"].iloc[-2]:
            return False
    
    if not (filters["rsi_min"] <= latest["rsi"] <= filters["rsi_max"]):
        return False
    
    if filters["kdj_cross"] == "K线上穿D线":
        if not (df["kdj_k"].iloc[-1] > df["kdj_d"].iloc[-1] and df["kdj_k"].iloc[-2] <= df["kdj_d"].iloc[-2]):
            return False
    if filters["kdj_cross"] == "K线下穿D线":
        if not (df["kdj_k"].iloc[-1] < df["kdj_d"].iloc[-1] and df["kdj_k"].iloc[-2] >= df["kdj_d"].iloc[-2]):
            return False
    
    if filters["bollinger"] == "突破上轨":
        if not (latest["close"] > latest["bollinger_high"]):
            return False
    if filters["bollinger"] == "跌破下轨":
        if not (latest["close"] < latest["bollinger_low"]):
            return False
    if filters["bollinger"] == "中轨附近":
        if not (abs(latest["close"] - latest["bollinger_mid"]) / latest["bollinger_mid"] < 0.02):
            return False
    
    return True

def run_screening():
    if "stock_pool" not in st.session_state or not st.session_state["stock_pool"]:
        st.warning("请先在侧边栏选择选股范围")
        return
    
    start_date = st.session_state.get("start_date")
    end_date = st.session_state.get("end_date")
    if not start_date or not end_date:
        st.warning("请先在侧边栏选择时间范围")
        return
    
    filters = st.session_state.get("filters", {})
    if not filters:
        filters = get_filter_conditions()
    
    progress_bar = st.progress(0, text="正在筛选股票...")
    results = []
    
    total = len(st.session_state["stock_pool"])
    for i, code in enumerate(st.session_state["stock_pool"]):
        progress_bar.progress((i+1)/total, text=f"正在处理 {code}...")
        df = fetch_daily_data(code, start_date, end_date)
        if df is None or df.empty:
            continue
        df = add_technical_indicators(df)
        if apply_filters(df, filters):
            stock_list = fetch_stock_list()
            name_row = stock_list[stock_list["code"] == code]
            name = name_row["name"].iloc[0] if not name_row.empty else code
            results.append({
                "代码": code,
                "名称": name,
                "最新价": df["close"].iloc[-1],
                "涨跌幅(%)": df["pct_change"].iloc[-1],
                "成交量(万股)": df["volume"].iloc[-1] / 10000,
                "RSI": df["rsi"].iloc[-1],
                "MACD": df["macd_diff"].iloc[-1],
                "数据": df
            })
        time.sleep(0.1)
    
    progress_bar.empty()
    st.session_state["screen_results"] = results
    st.success(f"筛选完成，共找到 {len(results)} 只股票")

# ===================== 回测核心函数 =====================
def backtest_strategy(df, signal_func):
    """
    通用回测框架
    signal_func: 函数，输入df，返回信号Series（1买入，-1卖出，0持有）
    """
    signals = signal_func(df)
    df = df.copy()
    df["signal"] = signals
    
    df["position"] = df["signal"].replace(0, np.nan).ffill().fillna(0)
    df["position"] = df["position"].clip(lower=0)
    
    df["returns"] = df["close"].pct_change()
    df["strategy_returns"] = df["position"].shift(1) * df["returns"]
    
    df["cumulative_returns"] = (1 + df["returns"]).cumprod()
    df["cumulative_strategy"] = (1 + df["strategy_returns"]).cumprod()
    
    total_return = df["cumulative_strategy"].iloc[-1] - 1
    benchmark_return = df["cumulative_returns"].iloc[-1] - 1
    
    cumulative = df["cumulative_strategy"]
    rolling_max = cumulative.expanding().max()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    return df, {
        "总收益率": total_return,
        "基准收益率": benchmark_return,
        "最大回撤": max_drawdown,
        "交易次数": (df["signal"] != 0).sum()
    }

# ===================== 策略函数库 =====================
def ma_cross_strategy(df, short=5, long=20):
    """均线金叉死叉策略"""
    signals = pd.Series(0, index=df.index)
    short_ma = df[f"ma{short}"]
    long_ma = df[f"ma{long}"]
    buy_signals = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
    sell_signals = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))
    signals[buy_signals] = 1
    signals[sell_signals] = -1
    return signals

def macd_cross_strategy(df):
    """MACD金叉死叉策略"""
    signals = pd.Series(0, index=df.index)
    buy_signals = (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
    sell_signals = (df["macd"] < df["macd_signal"]) & (df["macd"].shift(1) >= df["macd_signal"].shift(1))
    signals[buy_signals] = 1
    signals[sell_signals] = -1
    return signals

def rsi_strategy(df, oversold=30, overbought=70):
    """RSI超买超卖策略：超卖买入，超买卖出"""
    signals = pd.Series(0, index=df.index)
    buy_signals = (df["rsi"] < oversold) & (df["rsi"].shift(1) >= oversold)
    sell_signals = (df["rsi"] > overbought) & (df["rsi"].shift(1) <= overbought)
    signals[buy_signals] = 1
    signals[sell_signals] = -1
    return signals

def kdj_cross_strategy(df):
    """KDJ金叉死叉策略"""
    signals = pd.Series(0, index=df.index)
    buy_signals = (df["kdj_k"] > df["kdj_d"]) & (df["kdj_k"].shift(1) <= df["kdj_d"].shift(1))
    sell_signals = (df["kdj_k"] < df["kdj_d"]) & (df["kdj_k"].shift(1) >= df["kdj_d"].shift(1))
    signals[buy_signals] = 1
    signals[sell_signals] = -1
    return signals

# ===================== 直接回测界面（修改点：添加名称查询）=====================
def direct_backtest_ui():
    with st.sidebar:
        st.divider()
        st.title("🎯 直接回测")
        
        stock_code = st.text_input("股票代码", placeholder="例如 000001 或 000001.SZ", key="direct_code")
        
        strategy_option = st.selectbox(
            "选择策略",
            ["均线金叉", "MACD金叉", "RSI超买超卖", "KDJ金叉"],
            key="direct_strategy"
        )
        
        params = {}
        if strategy_option == "均线金叉":
            col1, col2 = st.columns(2)
            with col1:
                params["short"] = st.number_input("短期均线", min_value=2, max_value=50, value=5, step=1)
            with col2:
                params["long"] = st.number_input("长期均线", min_value=5, max_value=200, value=20, step=1)
        elif strategy_option == "RSI超买超卖":
            col1, col2 = st.columns(2)
            with col1:
                params["oversold"] = st.number_input("超卖线", min_value=10, max_value=40, value=30, step=1)
            with col2:
                params["overbought"] = st.number_input("超买线", min_value=60, max_value=90, value=70, step=1)
        
        if st.button("🚀 运行回测", use_container_width=True, key="run_direct_btn"):
            if not stock_code.strip():
                st.warning("请输入股票代码")
                return
            
            start_date = st.session_state.get("start_date")
            end_date = st.session_state.get("end_date")
            if not start_date or not end_date:
                st.warning("请先在时间范围中选择日期")
                return
            
            with st.spinner("正在获取数据并运行回测..."):
                df = fetch_daily_data(stock_code.strip(), start_date, end_date)
                if df is None or df.empty:
                    st.error(f"获取 {stock_code.strip()} 数据失败。可能原因：网络连接问题、股票代码错误、或该股票在所选时间段内无数据。请稍后重试或检查代码。")
                    return
                
                # 获取股票名称
                stock_list = fetch_stock_list()
                code_for_search = stock_code.strip().split('.')[0]  # 取纯数字部分
                name_row = stock_list[stock_list["code"] == code_for_search]
                name = name_row["name"].iloc[0] if not name_row.empty else stock_code.strip()
                
                df = add_technical_indicators(df)
                
                if strategy_option == "均线金叉":
                    signal_func = lambda d: ma_cross_strategy(d, params.get("short", 5), params.get("long", 20))
                elif strategy_option == "MACD金叉":
                    signal_func = macd_cross_strategy
                elif strategy_option == "RSI超买超卖":
                    signal_func = lambda d: rsi_strategy(d, params.get("oversold", 30), params.get("overbought", 70))
                elif strategy_option == "KDJ金叉":
                    signal_func = kdj_cross_strategy
                else:
                    signal_func = ma_cross_strategy
                
                result_df, metrics = backtest_strategy(df, signal_func)
                
                st.session_state["direct_result"] = {
                    "code": stock_code.strip(),
                    "name": name,  # 新增名称字段
                    "df": result_df,
                    "metrics": metrics,
                    "strategy": strategy_option
                }
                st.rerun()

# ===================== 主界面 =====================
def main():
    st.title("📈 智能选股工具（Tushare 数据源版）")
    
    with st.sidebar:
        st.header("配置面板")
    
    user_auth()
    manage_favorites()
    select_stock_pool()
    select_time_range()
    filters = get_filter_conditions()
    st.session_state["filters"] = filters
    
    direct_backtest_ui()
    
    if st.sidebar.button("🚀 开始选股", use_container_width=True):
        run_screening()
    
    tab1, tab2 = st.tabs(["📊 选股结果", "📈 直接回测"])
    
    with tab1:
        if "screen_results" in st.session_state and st.session_state["screen_results"]:
            st.subheader(f"选股结果 ({len(st.session_state['screen_results'])} 只)")
            
            results_df = pd.DataFrame(st.session_state["screen_results"])
            display_cols = ["代码", "名称", "最新价", "涨跌幅(%)", "成交量(万股)", "RSI", "MACD"]
            st.dataframe(results_df[display_cols], use_container_width=True, hide_index=True)
            
            for res in st.session_state["screen_results"]:
                with st.expander(f"{res['代码']} - {res['名称']}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("最新价", f"{res['最新价']:.2f}")
                    col2.metric("涨跌幅", f"{res['涨跌幅(%)']:.2f}%")
                    col3.metric("RSI", f"{res['RSI']:.2f}")
                    
                    df = res["数据"]
                    
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                         row_heights=[0.7, 0.3], vertical_spacing=0.05)
                    fig.add_trace(go.Candlestick(
                        x=df.index,
                        open=df["open"],
                        high=df["high"],
                        low=df["low"],
                        close=df["close"],
                        name="K线"
                    ), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df["ma5"], name="MA5", line=dict(color="blue")), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df["ma20"], name="MA20", line=dict(color="red")), row=1, col=1)
                    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量"), row=2, col=1)
                    
                    fig.update_layout(height=500, margin=dict(l=20, r=20, t=30, b=20))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if st.button(f"回测此股票 - {res['代码']}", key=f"backtest_{res['代码']}"):
                        result_df, metrics = backtest_strategy(df, ma_cross_strategy)
                        st.session_state["direct_result"] = {
                            "code": res['代码'],
                            "name": res['名称'],
                            "df": result_df,
                            "metrics": metrics,
                            "strategy": "均线金叉"
                        }
                        st.rerun()
        else:
            st.info("请在侧边栏配置筛选条件，然后点击「开始选股」")
    
    with tab2:
        if "direct_result" in st.session_state:
            res = st.session_state["direct_result"]
            # 使用名称显示（如果存在）
            display_name = res.get('name', res['code'])
            st.subheader(f"📊 回测结果 - {display_name} ({res['strategy']})")
            
            metrics = res["metrics"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("总收益率", f"{metrics['总收益率']*100:.2f}%")
            col2.metric("基准收益率", f"{metrics['基准收益率']*100:.2f}%")
            col3.metric("最大回撤", f"{metrics['最大回撤']*100:.2f}%")
            col4.metric("交易次数", metrics["交易次数"])
            
            df = res["df"]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df["cumulative_strategy"], name="策略收益"))
            fig.add_trace(go.Scatter(x=df.index, y=df["cumulative_returns"], name="基准收益"))
            fig.update_layout(title="策略收益 vs 基准", xaxis_title="日期", yaxis_title="累计收益")
            st.plotly_chart(fig, use_container_width=True)
            
            fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                  row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig2.add_trace(go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="K线"
            ), row=1, col=1)
            
            buy_signals = df[df["signal"] == 1]
            sell_signals = df[df["signal"] == -1]
            fig2.add_trace(go.Scatter(
                x=buy_signals.index, y=buy_signals["close"],
                mode="markers", name="买入",
                marker=dict(symbol="triangle-up", size=10, color="red")
            ), row=1, col=1)
            fig2.add_trace(go.Scatter(
                x=sell_signals.index, y=sell_signals["close"],
                mode="markers", name="卖出",
                marker=dict(symbol="triangle-down", size=10, color="green")
            ), row=1, col=1)
            
            fig2.add_trace(go.Scatter(x=df.index, y=df["ma5"], name="MA5", line=dict(color="blue")), row=1, col=1)
            fig2.add_trace(go.Scatter(x=df.index, y=df["ma20"], name="MA20", line=dict(color="red")), row=1, col=1)
            fig2.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量"), row=2, col=1)
            
            fig2.update_layout(height=600, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig2, use_container_width=True)
            
            if st.button("清除回测结果"):
                del st.session_state["direct_result"]
                st.rerun()
        else:
            st.info("请在侧边栏输入股票代码并点击「运行回测」")

if __name__ == "__main__":
    main()
