"""Cấu hình tập trung. Sửa ngưỡng, danh sách mã, tham số chỉ báo ở đây; code logic không cần đụng."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from storage.paths import repo_root

# --- Đường dẫn (mọi thứ cần giữ qua rebuild nằm trong data/, là volume đã mount) ---
APP_DIR = repo_root()
DATA_DIR = APP_DIR / "data"
SCAN_UNIVERSE_PATH = DATA_DIR / "scan_universe.csv"
POSITIONS_PATH = DATA_DIR / "positions.csv"
JOURNAL_PATH = DATA_DIR / "journal.csv"
ALERTS_PATH = DATA_DIR / "alerts.csv"
BULLETIN_PATH = DATA_DIR / "ban_tin.md"
BARS_DIR = DATA_DIR / "ohlcv"
FLOW_DIR = DATA_DIR / "flow"
INDUSTRY_PATH = DATA_DIR / "industry_l3.csv"
VALUATION_PATH = DATA_DIR / "valuation.csv"
EPS_DIR = DATA_DIR / "eps"
SIGNALS_DB = DATA_DIR / "signals.db"
WATCHLISTS_DIR = DATA_DIR / "watchlists"
KQKD_DIR = DATA_DIR / "kqkd"
POSTS_PATH = DATA_DIR / "member_posts.json"
NEWS_CACHE_PATH = DATA_DIR / "news_cache.json"

# --- Danh sách quét và bộ lọc Top 20 (ROE + thanh khoản + RS 3 tháng) ---
UNIVERSE = [
    "POW", "FPT", "HPG", "VNM", "SSI", "MWG", "TCB", "ACB", "VCB", "MBB",
    "STB", "VPB", "HDB", "VRE", "VHM", "VIC", "MSN", "GAS", "PLX", "SAB",
    "VJC", "BID", "CTG", "TPB", "MSB", "EIB", "PDR", "DIG", "DXG", "REE",
    "GMD", "PVS", "VCI", "HCM",
]
MIN_AVG_VOLUME = 100_000
MIN_ROE = 0.12
TOP_N = 20
RS_FILTER_OFF = -100.0   # sàn RS trên giao diện; mức này không cắt Top 20 mặc định
WORKERS = 8
SCAN_DAYS = 230          # số ngày lịch lấy giá khi quét
CHART_DAYS = 400         # số ngày lịch cho đồ thị (đủ ~52 tuần cho chữ N và mẫu cốc)
RS_LOOKBACK_DAYS = 91    # cửa sổ sức mạnh giá 3 tháng trong bộ lọc Top 20
MIN_BARS = 20
BARS_MAX_AGE_DAYS = 4
INDUSTRY_MAX_AGE_DAYS = 7
INDUSTRY_LEVEL = 3
MARKET_INDEX = "VNINDEX"
QUOTA_RETRIES = 6
QUOTA_SLEEP_SECONDS = 20

# --- Chỉ báo ---
MA_SHORT = 20
MA_MID = 50
MA_LONG = 150            # dùng nếu đủ dữ liệu
BB_LENGTH = 20
BB_STD = 2.0
RSI_LENGTH = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
ICHIMOKU_TENKAN = 9
ICHIMOKU_KIJUN = 26
ICHIMOKU_SENKOU_B = 52
ICHIMOKU_DISPLACEMENT = 26
# MCDX (Banker / Hot Money) theo bản RSI phổ biến ở Việt Nam, thang 0–20.
MCDX_BANKER_PERIOD = 50
MCDX_BANKER_BASE = 50.0
MCDX_BANKER_SENS = 1.5
MCDX_HOT_PERIOD = 40
MCDX_HOT_BASE = 30.0
MCDX_HOT_SENS = 0.7
MFI_LENGTH = 14
MFI_HOT = 80
MFI_COLD = 20
VOLUME_AVG = 20
VOLUME_SPIKE = 1.5       # KL phiên cuối / TB20 để ghi chú "đột biến"

# --- Hỗ trợ / đáy trung tâm ---
SUPPORT_DAYS = 183
SUPPORT_BAND = 0.015

# --- CANSLIM (ngưỡng tham khảo theo O'Neil, chỉnh tuỳ ý) ---
CANSLIM = {
    "C_EPS_GROWTH": 25.0,     # % EPS quý so cùng kỳ
    "A_ROE": 17.0,            # % ROE quý mới nhất
    "N_NEAR_HIGH": 0.85,      # giá >= 85% đỉnh 52 tuần
    "S_VOLUME_SURGE": 1.4,    # KL phiên cuối >= 1,4 lần TB 50 phiên
    "S_VOLUME_AVG": 50,
    "L_RS_PERCENTILE": 70.0,  # RS 3 tháng thuộc top 30% danh sách quét
    "M_MA": 50,               # VNINDEX trên MA50 và MA50 dốc lên
}

# --- Mẫu hình kỹ thuật (heuristic) ---
PATTERNS = {
    "FLAT_BASE_BARS": 25,        # ~5 tuần
    "FLAT_BASE_MAX_RANGE": 0.15, # biên độ cao-thấp <= 15%
    "TRIPLE_BOTTOM_BARS": 120,
    "TRIPLE_BOTTOM_TOL": 0.03,   # 3 đáy cách nhau <= 3%
    "PIVOT_ORDER": 5,            # cực trị cục bộ: thấp/cao nhất trong ±5 phiên
    "CUP_MIN_BARS": 35,
    "CUP_MAX_BARS": 250,
    "CUP_DEPTH_MIN": 0.12,
    "CUP_DEPTH_MAX": 0.40,
    "CUP_RIM_TOL": 0.10,         # hai miệng cốc chênh <= 10%
    "HANDLE_MAX_BARS": 25,
    "HANDLE_MAX_DEPTH": 0.15,
}

HN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
# Phiên HOSE, inclusive, tính bằng phút từ 0:00. Cuối tuần luôn ngoài phiên.
SESSION_MORNING = (9 * 60, 11 * 60 + 30)
SESSION_AFTERNOON = (13 * 60, 14 * 60 + 45)
THOUSAND_VND = 1000.0    # vnstock trả giá theo nghìn đồng
DEFAULT_CAPITAL = 100_000_000
CAPITAL_STEP = 1_000_000
RISK_MIN, RISK_MAX, RISK_DEFAULT = 1, 5, 2
CAPITAL_TRANCHES = 4
COLUMNS = ["Mã", "Giá", "RS 3 tháng (%)", "ROE (%)", "KLGD TB 20 phiên"]

# Nến đơn của phiên cuối (Murphy / Nison). Không dùng cho mẫu hình nhiều tuần.
CANDLE = {
    "DOJI_BODY_RATIO": 0.10,  # thân <= 10% biên độ
    "SHADOW_BODY": 2.0,       # bóng dài >= 2 lần thân
}

# --- Đồ thị (charts.py) ---
CHART = {
    "MAIN_HEIGHT": 600,
    "SUB_HEIGHT": 260,
    "BG": "#0e1117",
    "FONT": "#f0f2f6",
    "UP": "#3ddc97",
    "DOWN": "#ff6b6b",
    "MA20": "#f4a261",
    "MA50": "#e9c46a",
    "BB": "#4cc9f0",
    "BB_MID": "#90e0ef",
    "NECKLINE": "#c77dff",
    "VOL_AVG": "#f0f2f6",
    "RSI": "#c77dff",
    "MACD": "#4cc9f0",
    "MACD_SIGNAL": "#f4a261",
    "MFI": "#2a9d8f",
    "REF": "#888888",
}
