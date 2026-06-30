# -*- coding: utf-8 -*-
"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
THAY ĐỔI v1.3.8 – MODULE BẢN TIN CẢNH BÁO RỦI RO KHÍ HẬU:
  [NEW]  Export bản tin ra file HTML (mở tab mới để xem/in/lưu)
  [NEW]  Tách biệt chi tiết Bắp cải, Súp lơ, Dưa chuột, Bí xanh thay cho "Rau" chung
  [NEW]  Tự động ẩn/hiện rau theo mùa vụ trong Bản tin cảnh báo rủi ro khí hậu
         (vd: Bắp cải trái vụ hè sẽ tự ẩn, vào vụ đông sẽ tự hiện)
THAY ĐỔI v1.3.9 – MODULE TỔNG QUAN:
  [NEW]  Chèn ảnh nền Quảng Ninh cho banner module Tổng quan
  [NEW]  Header gồm logo Viện + tên Viện, bấm vào sẽ liên kết tới Cổng TTĐT
         Sở Khoa học và Công nghệ tỉnh Quảng Ninh
  [KEEP] Giữ nguyên toàn bộ code cấu trúc giao diện v1.3.4
"""

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep
from shapely.wkt import loads as wkt_loads
import geopandas as gpd
import requests
import xarray as xr
import pandas as pd
import io
import os
import re
import base64
import tempfile
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
# CẤU HÌNH TRANG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Bản tin Khí hậu Quảng Ninh",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }
    header[data-testid="stHeader"] { height: 0rem !important; min-height: 0rem !important; }
    .module-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%);
        color: white; padding: 10px 20px; border-radius: 8px;
        font-size: 1.1rem; font-weight: bold; margin-top: 0; margin-bottom: 8px;
        display: flex; align-items: center; gap: 8px;
    }
    .risk-header {
        background: linear-gradient(135deg, #7b2d00 0%, #c0392b 100%);
        color: white; padding: 8px 16px; border-radius: 6px;
        font-size: 1rem; font-weight: bold; margin: 8px 0 4px 0;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e8f4f8; border-radius: 6px 6px 0 0;
        padding: 8px 16px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background-color: #1e3a5f !important; color: white !important; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e3a5f 0%, #2d3748 100%); }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
    .risk-0 { background-color: #f0f0f0 !important; color: #555 !important; }
    .risk-1 { background-color: #c8f7c5 !important; color: #1a5e20 !important; font-weight: bold; }
    .risk-2 { background-color: #fff176 !important; color: #7d6608 !important; font-weight: bold; }
    .risk-3 { background-color: #ff8a65 !important; color: #7d1f00 !important; font-weight: bold; }
    .commune-title {
        background: linear-gradient(90deg, #1e3a5f, #2d6a4f);
        color: white; padding: 8px 16px; border-radius: 8px;
        font-size: 1.2rem; font-weight: bold; margin: 0 0 8px 0;
        text-align: center;
    }
    .export-toolbar {
        display: flex; justify-content: flex-end; align-items: center;
        margin: 4px 0 10px 0;
    }
    .org-header {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 18px; margin-bottom: 12px;
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
    }
    .org-header img {
        height: 48px; width: 48px; object-fit: contain; border-radius: 6px; flex-shrink: 0;
    }
    .org-header .org-logo-fallback {
        height: 48px; width: 48px; flex-shrink: 0; display: flex; align-items: center;
        justify-content: center; font-size: 26px; background: #eef3f6; border-radius: 6px;
    }
    .org-header .org-text a {
        color: #1e3a5f; text-decoration: none; font-weight: 700; font-size: 1.05rem;
    }
    .org-header .org-text a:hover { color: #2d6a4f; text-decoration: underline; }
    .org-header .org-sub { font-size: 0.78rem; color: #667085; margin-top: 2px; }
    .hero-banner {
        position: relative; border-radius: 14px; overflow: hidden; margin-bottom: 18px;
        background-size: cover; background-position: center; min-height: 260px;
        display: flex; align-items: flex-end;
    }
    .hero-banner::before {
        content: ""; position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(30,58,95,0.18) 0%, rgba(13,26,43,0.82) 100%);
    }
    .hero-content { position: relative; z-index: 1; padding: 26px 28px; color: #fff; }
    .hero-content h1 { margin: 0 0 8px 0; font-size: 1.65rem; line-height: 1.3; }
    .hero-content p { margin: 0; font-size: 0.96rem; opacity: 0.95; max-width: 760px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL        = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
XACSUAT_URL     = "http://222.254.32.10/forecast/Detai_QuangNinh/xacsuat/domain_d02/"
MEMBER_URL      = "http://222.254.32.10/forecast/Detai_QuangNinh/trungbinhmember/domain_d02/"
SHP_QN_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"
SHP_XA_ROI_URL  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/xa_roi/"
ERA5_R_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/R_ERA5_CDFT_corrected.xlsx"
ERA5_T_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/T2m_ERA5_QM_corrected.xlsx"
COMMUNE_LONLAT_URL = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/lon_lat_quangninh.xlsx"

# Ảnh nền + thông tin header cho module "Tổng quan"
TONGQUAN_BG_URL    = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/anh_dep_quang_ninh_giao_dien_1.jpg"
INSTITUTE_LOGO_URL = ""  # TODO: dán URL ảnh logo Viện vào đây (vd: link raw.githubusercontent.com tới file logo .png/.jpg)
INSTITUTE_NAME      = "Viện Khoa học Khí tượng Thủy văn Môi trường và Biển"
DOST_QUANGNINH_URL  = "https://www.quangninh.gov.vn/so/sokhoahoccongnghe/trang/default.aspx"

CLIMATE_VARS = {
    "ano.T2m":  {"label": "Nhiệt độ trung bình (T2m)", "unit": "°C",  "cmap": "RdBu_r", "levels": list(range(-5, 6))},
    "ano.Tx":   {"label": "Nhiệt độ tối cao (Tx)",      "unit": "°C",  "cmap": "RdBu_r", "levels": list(range(-5, 6))},
    "ano.Tm":   {"label": "Nhiệt độ tối thấp (Tm)",     "unit": "°C",  "cmap": "RdBu_r", "levels": list(range(-5, 6))},
    "ano.R":    {"label": "Lượng mưa (R)",               "unit": "mm",  "cmap": "BrBG",   "levels": [-150,-100,-50,-25,-10,0,10,25,50,100,150]},
    "ano.RH2m": {"label": "Độ ẩm tương đối (RH2m)",     "unit": "%",   "cmap": "BrBG",   "levels": list(range(-20, 22, 4))},
}

EXTREME_VARS = {
    "ano.CDD":    {"label": "Số ngày khô liên tiếp (CDD)",    "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-10, 12, 2))},
    "ano.CWD":    {"label": "Số ngày ướt liên tiếp (CWD)",    "unit": "ngày", "cmap": "RdYlBu",   "levels": list(range(-10, 12, 2))},
    "ano.FD13":   {"label": "Số ngày lạnh <13°C (FD13)",      "unit": "ngày", "cmap": "RdBu",     "levels": list(range(-5, 6))},
    "ano.FD15":   {"label": "Số ngày lạnh <15°C (FD15)",      "unit": "ngày", "cmap": "RdBu",     "levels": list(range(-5, 6))},
    "ano.Rx1day": {"label": "Mưa 1 ngày cực đại (Rx1day)",    "unit": "mm",   "cmap": "BrBG",     "levels": [-100,-50,-25,-10,0,10,25,50,100]},
    "ano.Rx5day": {"label": "Mưa 5 ngày cực đại (Rx5day)",    "unit": "mm",   "cmap": "BrBG",     "levels": [-150,-75,-25,0,25,75,150]},
    "ano.SU35":   {"label": "Số ngày nắng nóng ≥35°C (SU35)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-10, 12, 2))},
    "ano.SU37":   {"label": "Số ngày nắng nóng ≥37°C (SU37)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-8, 10, 2))},
    "ano.SU39":   {"label": "Số ngày nắng nóng ≥39°C (SU39)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-6, 8, 2))},
    "ano.Evap":   {"label": "Bốc hơi (Evap)",                 "unit": "mm",   "cmap": "BrBG",     "levels": [-100,-50,-25,-10,0,10,25,50,100]},
}

# Tách riêng đối tượng rau trong các xã
COMMUNE_CROPS = {
    "Hải Sơn":    ["Lợn"],
    "Hải Ninh":   ["Lợn"],
    "Móng Cái 1": ["Lợn"],
    "Móng Cái 2": ["Lợn"],
    "Móng Cái 3": ["Lợn"],
    "Quảng Hà":   ["Lúa", "Bắp cải", "Dưa chuột", "Lợn", "Gà"],
    "Đường Hoa":  ["Lúa", "Súp lơ", "Bí xanh", "Lợn", "Gà"],
    "Quảng Đức":  ["Lúa", "Bắp cải", "Bí xanh", "Lợn", "Gà"],
    "Cái Chiên":  ["Lúa", "Dưa chuột", "Lợn", "Gà"],
    "Quảng Tân":  ["Lúa", "Súp lơ", "Bắp cải", "Lợn", "Gà"],
    "Đầm Hà":     ["Lúa", "Bí xanh", "Dưa chuột", "Lợn", "Gà"],
    "Hải Hòa":    ["Bắp cải", "Dưa chuột", "Gà"],
    "Tiên Yên":   ["Súp lơ", "Bí xanh", "Gà"],
    "Điền Xá":    ["Bắp cải", "Dưa chuột", "Gà"],
    "Đông Ngũ":   ["Súp lơ", "Bí xanh", "Gà"],
    "Hải Lạng":   ["Bắp cải", "Súp lơ", "Gà"],
    "Đông Mai":   ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
    "Hiệp Hòa":   ["Lúa", "Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "Quang Yên":  ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
    "Hà An":      ["Lúa", "Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "Phong Cốc":  ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
    "Liên Hòa":   ["Lúa", "Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "Yên Tử":     ["Bắp cải", "Bí xanh", "Lợn", "Gà"],
    "Vàng Danh":  ["Súp lơ", "Dưa chuột", "Lợn", "Gà"],
    "Uông Bí":    ["Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "An Sinh":    ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
    "Đông Triều": ["Lúa", "Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "Bình Khuê":  ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
    "Mạo Khê":    ["Lúa", "Bắp cải", "Súp lơ", "Lợn", "Gà"],
    "Hoàng Quế":  ["Lúa", "Dưa chuột", "Bí xanh", "Lợn", "Gà"],
}

COMMUNE_COL_MAP = {
    "Hải Sơn":    "haison", "Hải Ninh":   "haininh", "Móng Cái 1": "mongcai1", "Móng Cái 2": "mongcai2", "Móng Cái 3": "mongcai3",
    "Quảng Hà":   "quangha", "Đường Hoa":  "duonghoa", "Quảng Đức":  "quangduc", "Cái Chiên":  "caichien", "Quảng Tân":  "quangtan",
    "Đầm Hà":     "damha", "Hải Hòa":    "haihoa", "Tiên Yên":   "tienyen", "Điền Xá":    "dienxa", "Đông Ngũ":   "dongngu",
    "Hải Lạng":   "hailang", "Đông Mai":   "dongmai", "Hiệp Hòa":   "hiephoa", "Quang Yên":  "quangyen", "Hà An":      "haan",
    "Phong Cốc":  "phongcoc", "Liên Hòa":   "lienhoa", "Yên Tử":     "yentu", "Vàng Danh":  "vangdanh", "Uông Bí":    "uongbi",
    "An Sinh":    "ansinh", "Đông Triều": "dongtrieu", "Bình Khuê":  "binhkhe", "Mạo Khê":    "maokhe", "Hoàng Quế":  "hoangque",
}

# ══════════════════════════════════════════════════════════════════════════════
# ĐỘNG LỰC HỌC MÙA VỤ 12 THÁNG TÁCH BIỆT CHO 4 CÂY RAU + LÚA + VẬT NUÔI
# ══════════════════════════════════════════════════════════════════════════════

LUA_GROWTH_STAGES = {
    "T1/1": "Gieo, nảy mầm", "T2/1": "Mạ", "T3/1": "Mạ",
    "T1/2": "Đẻ nhánh", "T2/2": "Đẻ nhánh", "T3/2": "Đẻ nhánh",
    "T1/3": "Làm đòng", "T2/3": "Làm đòng", "T3/3": "Phân hóa hoa",
    "T1/4": "Trỗ – thụ phấn", "T2/4": "Chắc hạt", "T3/4": "Chắc hạt",
    "T1/5": "Chín, thu hoạch", "T2/5": "Chín, thu hoạch", "T3/5": "Nghỉ",
    "T1/6": "Gieo, nảy mầm", "T2/6": "Gieo, nảy mầm", "T3/6": "Mạ",
    "T1/7": "Mạ", "T2/7": "Đẻ nhánh", "T3/7": "Đẻ nhánh",
    "T1/8": "Làm đòng", "T2/8": "Phân hóa hoa", "T3/8": "Trỗ – thụ phấn",
    "T1/9": "Chắc hạt", "T2/9": "Chắc hạt", "T3/9": "Chín, thu hoạch",
    "T1/10": "Nghỉ", "T2/10": "Nghỉ", "T3/10": "Nghỉ",
    "T1/11": "Nghỉ", "T2/11": "Nghỉ", "T3/11": "Gieo, nảy mầm",
    "T1/12": "Gieo, nảy mầm", "T2/12": "Gieo, nảy mầm", "T3/12": "Gieo, nảy mầm",
}

# 1. Bắp cải (Đông Xuân)
BAPCAI_GROWTH_STAGES = {f"T{d}/{m}": "Nghỉ" for m in range(1, 13) for d in range(1, 4)}
BAPCAI_GROWTH_STAGES.update({
    "T1/9": "Gieo, nảy mầm", "T2/9": "Cây con", "T3/9": "Cây có 1-2 lá thật",
    "T1/10": "Trải lá", "T2/10": "Cuốn bắp", "T3/10": "Cuốn bắp",
    "T1/11": "Chắc bắp", "T2/11": "Thu hoạch sớm", "T3/11": "Thu hoạch",
    "T1/12": "Gieo đợt 2", "T2/12": "Cây con đợt 2", "T3/12": "Trải lá",
    "T1/1": "Cuốn bắp", "T2/1": "Thu hoạch", "T3/1": "Thu hoạch",
})

# 2. Súp lơ (Đông Xuân)
SUPLO_GROWTH_STAGES = {f"T{d}/{m}": "Nghỉ" for m in range(1, 13) for d in range(1, 4)}
SUPLO_GROWTH_STAGES.update({
    "T1/9": "Gieo, nảy mầm", "T2/9": "Cây con", "T3/9": "Cây con",
    "T1/10": "Phân hóa mầm hoa", "T2/10": "Hình thành nụ hoa", "T3/10": "Phát triển nụ hoa",
    "T1/11": "Phát triển nụ hoa", "T2/11": "Thu hoạch sớm", "T3/11": "Thu hoạch",
    "T1/12": "Gieo đợt 2", "T2/12": "Cây con đợt 2", "T3/12": "Phân hóa mầm hoa",
    "T1/1": "Phát triển nụ hoa", "T2/1": "Thu hoạch", "T3/1": "Thu hoạch",
})

# 3. Dưa chuột (Xuân Hè & Hè Thu)
DUACHUOT_GROWTH_STAGES = {f"T{d}/{m}": "Nghỉ" for m in range(1, 13) for d in range(1, 4)}
DUACHUOT_GROWTH_STAGES.update({
    "T1/2": "Nảy mầm", "T2/2": "Cây con", "T3/2": "Sinh trưởng thân lá",
    "T1/3": "Ra hoa - Đậu quả", "T2/3": "Phát triển quả", "T3/3": "Phát triển quả",
    "T1/4": "Thu hoạch", "T2/4": "Thu hoạch",
    "T3/6": "Ra hoa - Đậu quả",
    "T1/7": "Nảy mầm", "T2/7": "Cây con", "T3/7": "Sinh trưởng thân lá",
    "T1/8": "Ra hoa - Đậu quả", "T2/8": "Ra hoa - Đậu quả", "T3/8": "Thu hoạch",
})

# 4. Bí xanh (Xuân Hè & Hè Thu)
BIXANH_GROWTH_STAGES = {f"T{d}/{m}": "Nghỉ" for m in range(1, 13) for d in range(1, 4)}
BIXANH_GROWTH_STAGES.update({
    "T1/2": "Nảy mầm", "T2/2": "Cây con", "T3/2": "Sinh trưởng thân lá",
    "T1/3": "Sinh trưởng thân lá", "T2/3": "Phát triển hoa, quả", "T3/3": "Phát triển quả",
    "T1/4": "Phát triển quả", "T2/4": "Thu hoạch", "T3/4": "Thu hoạch",
    "T1/5": "Làm đất", "T3/5": "Gieo, nảy mầm",
    "T1/6": "Sinh trưởng thân lá", "T2/6": "Ra hoa", "T3/6": "Đậu quả",
    "T1/7": "Phát triển quả", "T2/7": "Phát triển quả", "T3/7": "Sinh trưởng thân lá",
    "T1/8": "Thu hoạch", "T2/8": "Thu hoạch",
})

LON_GROWTH_STAGES = {f"T{d}/{m}": "Sinh trưởng & Vỗ béo" for m in range(1, 13) for d in range(1, 4)}
GA_GROWTH_STAGES = {f"T{d}/{m}": "Sinh trưởng & Đẻ trứng" for m in range(1, 13) for d in range(1, 4)}

LUA_TEMP_RISK = {
    "Gieo, nảy mầm": (10, 45), "Mạ": (12, 35), "Đẻ nhánh": (9,  33),
    "Làm đòng": (15, 38), "Phân hóa hoa": (15, 38), "Trỗ – thụ phấn": (22, 38),
    "Chắc hạt": (12, 35), "Chín, thu hoạch": (12, 35), "Nghỉ": (0, 99),
}

PIG_THI_RISK = {"normal": 74, "warn": 78, "danger": 83, "critical": 84}
CHICKEN_THI_RISK = {"normal": 70, "warn": 75, "danger": 81, "critical": 81}

RISK_LABELS = {0: "—", 1: "Thấp", 2: "Trung bình", 3: "Cao"}
RISK_COLORS = {0: "#f0f0f0", 1: "#c8f7c5", 2: "#fff176", 3: "#ff8a65"}

# ══════════════════════════════════════════════════════════════════════════════
# FIX ENCODING UTF-8
# ══════════════════════════════════════════════════════════════════════════════

def _fix_encoding(val):
    if not isinstance(val, str):
        return val
    try:
        return val.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return val

def _fix_gdf_text(gdf):
    gdf.columns = [_fix_encoding(c) for c in gdf.columns]
    for col in gdf.select_dtypes(include="object").columns:
        try:
            gdf[col] = gdf[col].apply(_fix_encoding)
        except Exception:
            pass
    return gdf

# ══════════════════════════════════════════════════════════════════════════════
# LOAD SHAPEFILE & DỮ LIỆU
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_shapefiles():
    exts = [".shp", ".dbf", ".shx", ".prj"]
    tmp_dir = tempfile.mkdtemp()
    def _download_shp(name):
        all_ok = True
        for ext in exts:
            r = requests.get(SHP_QN_URL + name + ext, timeout=30)
            if r.status_code == 200:
                with open(os.path.join(tmp_dir, name + ext), "wb") as f:
                    f.write(r.content)
            else:
                all_ok = False
        shp_path = os.path.join(tmp_dir, name + ".shp")
        return shp_path if all_ok and os.path.exists(shp_path) else None

    def _read_safe(path):
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1258"):
            try:
                gdf = gpd.read_file(path, encoding=enc)
                if gdf.crs and gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(epsg=4326)
                if enc in ("latin-1", "cp1258"):
                    gdf = _fix_gdf_text(gdf)
                return gdf
            except Exception:
                continue
        return None

    gdf_all_tinh = gdf_tinh_qn = gdf_xa = None
    try:
        p = _download_shp("RG_34TINH")
        if p:
            gdf_all = _read_safe(p)
            if gdf_all is not None:
                gdf_all_tinh = gdf_all.copy()
                qn_mask = None
                for col in gdf_all.columns:
                    cu = col.upper()
                    if cu in ("TINH", "TEN_TINH", "PROVINCE", "NAME"):
                        qn_mask = gdf_all[col].str.contains("Quảng Ninh|Quang Ninh", case=False, na=False)
                        break
                    elif cu in ("MATINH", "MA_TINH", "TINH_CD", "PROVCODE", "MA"):
                        try: qn_mask = gdf_all[col].astype(str).str.strip() == "22"
                        except Exception: pass
                        break
                if qn_mask is not None and qn_mask.any():
                    gdf_tinh_qn = gdf_all[qn_mask].copy()
    except Exception: pass

    try:
        p = _download_shp("xa_quangninh")
        if p: gdf_xa = _read_safe(p)
    except Exception: pass

    return gdf_all_tinh, gdf_tinh_qn, gdf_xa

@st.cache_resource(show_spinner=False)
def load_commune_shp(col_key: str):
    if not col_key: return None
    exts = [".shp", ".dbf", ".shx", ".prj"]
    tmp_dir = tempfile.mkdtemp()
    all_ok = True
    for ext in exts:
        url = SHP_XA_ROI_URL + col_key + ext
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                with open(os.path.join(tmp_dir, col_key + ext), "wb") as f:
                    f.write(r.content)
            else:
                all_ok = False
        except Exception:
            all_ok = False

    shp_path = os.path.join(tmp_dir, col_key + ".shp")
    if not all_ok or not os.path.exists(shp_path): return None

    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1258"):
        try:
            gdf = gpd.read_file(shp_path, encoding=enc)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            return gdf
        except Exception: continue
    return None

@st.cache_resource(show_spinner=False)
def build_boundary_traces_cached(_gdf_all_tinh, _gdf_tinh_qn, _gdf_xa):
    def _geom_to_xy(gdf):
        all_x, all_y = [], []
        for geom in gdf.geometry:
            if geom is None or geom.is_empty: continue
            polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            for poly in polys:
                xs, ys = poly.exterior.xy
                all_x.extend(list(xs)); all_x.append(None)
                all_y.extend(list(ys)); all_y.append(None)
        return all_x, all_y

    def _xa_labels(gdf_xa):
        name_col = None
        for col in gdf_xa.columns:
            if col.upper() in ("TEN_XA", "TENXA", "XA", "NAME", "TEN"):
                name_col = col; break
        if name_col is None:
            for col in gdf_xa.columns:
                if col.lower() != "geometry":
                    name_col = col; break
        xs, ys, texts = [], [], []
        for _, row in gdf_xa.iterrows():
            try:
                c = row.geometry.centroid
                xs.append(c.x); ys.append(c.y)
                texts.append(_fix_encoding(str(row[name_col])) if name_col else "")
            except Exception: pass
        return xs, ys, texts

    result = {}
    if _gdf_all_tinh is not None and not _gdf_all_tinh.empty:
        result["tinh_x"], result["tinh_y"] = _geom_to_xy(_gdf_all_tinh)
    if _gdf_tinh_qn is not None and not _gdf_tinh_qn.empty:
        result["qn_x"], result["qn_y"] = _geom_to_xy(_gdf_tinh_qn)
        result["mask_wkt"] = _gdf_tinh_qn.unary_union.wkt
        result["bounds"]   = tuple(_gdf_tinh_qn.total_bounds)
    if _gdf_xa is not None and not _gdf_xa.empty:
        result["xa_x"], result["xa_y"] = _geom_to_xy(_gdf_xa)
        result["xa_lx"], result["xa_ly"], result["xa_texts"] = _xa_labels(_gdf_xa)
        if "bounds" not in result:
            result["bounds"]   = tuple(_gdf_xa.total_bounds)
            result["mask_wkt"] = _gdf_xa.unary_union.wkt
    return result

@st.cache_data(ttl=86400, show_spinner=False)
def load_era5_data():
    try:
        r_r = requests.get(ERA5_R_URL, timeout=30)
        r_t = requests.get(ERA5_T_URL, timeout=30)
        if r_r.status_code != 200 or r_t.status_code != 200: return None, None
        df_r = pd.read_excel(io.BytesIO(r_r.content), sheet_name=0, header=None)
        df_t = pd.read_excel(io.BytesIO(r_t.content), sheet_name=0, header=None)

        cols_r = df_r.iloc[0].tolist()
        df_r.columns = cols_r
        df_r = df_r.iloc[3:].copy()
        df_r = df_r.rename(columns={"year": "year", "month": "month", "day": "day"})
        for c in ["year", "month", "day"]: df_r[c] = pd.to_numeric(df_r[c], errors="coerce")
        df_r = df_r.dropna(subset=["year", "month", "day"])
        df_r[["year","month","day"]] = df_r[["year","month","day"]].astype(int)

        cols_t = df_t.iloc[0].tolist()
        df_t.columns = cols_t
        df_t = df_t.iloc[3:].copy()
        for c in ["year", "month", "day"]: df_t[c] = pd.to_numeric(df_t[c], errors="coerce")
        df_t = df_t.dropna(subset=["year", "month", "day"])
        df_t[["year","month","day"]] = df_t[["year","month","day"]].astype(int)
        return df_r, df_t
    except Exception:
        return None, None

def get_commune_monthly_climate(commune_name, df_r, df_t):
    col_key = COMMUNE_COL_MAP.get(commune_name)
    if col_key is None or df_r is None or df_t is None: return {}
    mask_r = (df_r["year"] >= 1981) & (df_r["year"] <= 2024)
    mask_t = (df_t["year"] >= 1981) & (df_t["year"] <= 2024)

    r_col = next((c for c in df_r.columns if str(c).lower().strip() == col_key.lower()), None)
    t_col = next((c for c in df_t.columns if str(c).lower().strip() == col_key.lower()), None)
    if r_col is None or t_col is None: return {}

    sub_r = df_r[mask_r][["year","month","day", r_col]].copy()
    sub_t = df_t[mask_t][["year","month","day", t_col]].copy()
    sub_r[r_col] = pd.to_numeric(sub_r[r_col], errors="coerce")
    sub_t[t_col] = pd.to_numeric(sub_t[t_col], errors="coerce")

    result = {}
    for m in range(1, 13):
        r_m = sub_r[sub_r["month"] == m]
        t_m = sub_t[sub_t["month"] == m]
        rain_monthly = r_m.groupby("year")[r_col].sum().mean()
        temp_monthly = t_m[t_col].mean()
        result[m] = {"T": round(float(temp_monthly), 1) if not np.isnan(temp_monthly) else 0,
                     "R": round(float(rain_monthly), 1) if not np.isnan(rain_monthly) else 0}
    return result

@st.cache_data(ttl=86400, show_spinner=False)
def load_commune_lonlat():
    try:
        r = requests.get(COMMUNE_LONLAT_URL, timeout=30)
        if r.status_code != 200: return {}
        df = pd.read_excel(io.BytesIO(r.content), sheet_name=0, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        key_col = next((c for c in df.columns if c.lower() in ("year", "ma_xa", "key", "xa", "commune")), df.columns[0])
        lon_col = next((c for c in df.columns if c.upper() == "LON"), None)
        lat_col = next((c for c in df.columns if c.upper() == "LAT"), None)
        if lon_col is None or lat_col is None: return {}

        result = {}
        for _, row in df.iterrows():
            key = str(row[key_col]).strip().lower()
            try:
                lon = float(row[lon_col])
                lat = float(row[lat_col])
                if np.isfinite(lon) and np.isfinite(lat): result[key] = (lon, lat)
            except (TypeError, ValueError): continue
        return result
    except Exception: return {}

def get_commune_lonlat(commune_name, commune_lonlat_map):
    col_key = COMMUNE_COL_MAP.get(commune_name, "")
    if not col_key or not commune_lonlat_map: return None, None
    return commune_lonlat_map.get(col_key.lower(), (None, None))

# ══════════════════════════════════════════════════════════════════════════════
# NETCDF & MEMBER DATA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_available_periods() -> list:
    try:
        resp = requests.get(BASE_URL, timeout=10)
        resp.raise_for_status()
        return sorted(set(re.findall(r'(\d{6})/', resp.text)))
    except Exception as e:
        st.warning(f"⚠️ Không thể lấy danh sách thư mục: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def download_nc(period: str, var_prefix: str, base_url: str = None):
    if base_url is None: base_url = BASE_URL
    url = f"{base_url}{period}/{var_prefix}.{period}.nc"
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.status_code == 200 else None
    except Exception: return None

@st.cache_data(ttl=3600, show_spinner=False)
def load_nc_data(nc_bytes: bytes, month_idx: int):
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        coord_names = {c.lower() for c in ds.coords}
        data_vars = [v for v in ds.data_vars if v.lower() not in coord_names]
        if not data_vars: return None, None, None, "Không tìm thấy biến dữ liệu"
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'month' in d.lower()]
        if time_dims: da = da.isel({time_dims[0]: min(month_idx, da.sizes[time_dims[0]] - 1)})
        lat_names = [d for d in da.dims if 'lat' in d.lower() or d == 'y']
        lon_names = [d for d in da.dims if 'lon' in d.lower() or d == 'x']
        if not lat_names or not lon_names: return None, None, None, "Không tìm thấy chiều lat/lon"
        lats, lons = da[lat_names[0]].values, da[lon_names[0]].values
        vals = da.values
        if lons.ndim == 1: lons, lats = np.meshgrid(lons, lats)
        flat_lon, flat_lat, flat_val = lons.ravel(), lats.ravel(), vals.ravel()
        ok = np.isfinite(flat_val) & (np.abs(flat_val) < 1e10)
        ds.close(); os.unlink(tmp)
        return flat_lon[ok], flat_lat[ok], flat_val[ok], None
    except Exception as e:
        try: os.unlink(tmp)
        except: pass
        return None, None, None, str(e)

# PROBABILITY
XACSUAT_CATEGORY_PREFIX = {"thap_hon": "XSHC", "xap_xi": "XSCC", "cao_hon": "XSVC"}

@st.cache_data(ttl=3600, show_spinner=False)
def download_xacsuat_nc(period: str, category_prefix: str, var_name: str):
    url = f"{XACSUAT_URL}{period}/{category_prefix}.{var_name}.nc"
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.status_code == 200 else None
    except Exception: return None

@st.cache_data(ttl=3600, show_spinner=False)
def _extract_xacsuat_grid(nc_bytes: bytes, month_idx: int):
    if nc_bytes is None: return None, None, None
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        coord_names = {c.lower() for c in ds.coords}
        data_vars = [v for v in ds.data_vars if v.lower() not in coord_names]
        if not data_vars: ds.close(); os.unlink(tmp); return None, None, None
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower()]
        if time_dims: da = da.isel({time_dims[0]: min(month_idx, da.sizes[time_dims[0]] - 1)})
        lat_names = [d for d in da.dims if 'lat' in d.lower() or d == 'y']
        lon_names = [d for d in da.dims if 'lon' in d.lower() or d == 'x']
        if not lat_names or not lon_names: ds.close(); os.unlink(tmp); return None, None, None
        lats = da[lat_names[0]].values
        lons = da[lon_names[0]].values
        vals = da.values
        if lons.ndim == 1: lons, lats = np.meshgrid(lons, lats)
        flat_lon, flat_lat, flat_val = lons.ravel(), lats.ravel(), vals.ravel().astype(float)
        ok = np.isfinite(flat_val) & (np.abs(flat_val) < 1e10)
        ds.close(); os.unlink(tmp)
        return flat_lon[ok], flat_lat[ok], flat_val[ok]
    except Exception:
        try: os.unlink(tmp)
        except Exception: pass
        return None, None, None

def _point_value_idw(lons, lats, vals, lon_c, lat_c, k=4, power=2.0, eps=1e-9):
    if lons is None or lons.size == 0 or lon_c is None or lat_c is None: return None
    try:
        tree = cKDTree(np.column_stack([lons, lats]))
        kk = min(k, lons.size)
        dists, idxs = tree.query([lon_c, lat_c], k=kk)
        dists = np.atleast_1d(dists)
        idxs = np.atleast_1d(idxs)
        if np.any(dists <= eps): return float(vals[idxs[np.argmin(dists)]])
        w = 1.0 / np.maximum(dists, eps) ** power
        return float(np.sum(w * vals[idxs]) / np.sum(w))
    except Exception: return None

def _extract_prob_at_point(period, var_name, month_idx, lon_c, lat_c):
    raw_vals = []
    for cat_key in ("thap_hon", "xap_xi", "cao_hon"):
        prefix = XACSUAT_CATEGORY_PREFIX[cat_key]
        nc_bytes = download_xacsuat_nc(period, prefix, var_name)
        lons, lats, vals = _extract_xacsuat_grid(nc_bytes, month_idx) if nc_bytes else (None, None, None)
        v = _point_value_idw(lons, lats, vals, lon_c, lat_c)
        raw_vals.append(v)
    if any(v is None for v in raw_vals): return (None, None, None)
    total = sum(raw_vals)
    if total <= 0: return (None, None, None)
    return tuple(round(v / total * 100) for v in raw_vals)

@st.cache_data(ttl=3600, show_spinner=False)
def load_xacsuat_for_commune(period: str, commune_name: str, lon_c, lat_c, month_offsets=(1, 2, 3)):
    result = {}
    yr, mo = int(period[:4]), int(period[4:])
    if lon_c is None or lat_c is None:
        for offset in month_offsets:
            m2 = ((mo + offset - 1) % 12) + 1
            y2 = yr + (mo + offset - 1) // 12
            result[f"Tháng {m2:02d}/{y2}"] = {"T": (None, None, None), "R": (None, None, None)}
        return result
    for offset in month_offsets:
        m2 = ((mo + offset - 1) % 12) + 1
        y2 = yr + (mo + offset - 1) // 12
        label = f"Tháng {m2:02d}/{y2}"
        month_idx = offset - 1
        result[label] = {
            "T": _extract_prob_at_point(period, "T2m", month_idx, lon_c, lat_c),
            "R": _extract_prob_at_point(period, "R", month_idx, lon_c, lat_c)
        }
    return result

@st.cache_data(ttl=3600, show_spinner=False)
def load_member_decadal(period: str, month_offsets=(1,2,3)):
    yr, mo = int(period[:4]), int(period[4:])
    rows = []
    for offset in month_offsets:
        m2 = ((mo + offset - 1) % 12) + 1
        for decade_idx, decade_label in enumerate(["T1", "T2", "T3"]):
            label = f"{decade_label}/{m2}"
            t_bytes = download_nc(period, "T2m", MEMBER_URL)
            rh_bytes = download_nc(period, "RH2m", MEMBER_URL)
            r_bytes = download_nc(period, "R", MEMBER_URL)
            rows.append({
                "decade": label,
                "T2m": _extract_decadal_mean(t_bytes, offset - 1, decade_idx, is_sum=False),
                "RH2m": _extract_decadal_mean(rh_bytes, offset - 1, decade_idx, is_sum=False),
                "R": _extract_decadal_mean(r_bytes, offset - 1, decade_idx, is_sum=True),
            })
    return pd.DataFrame(rows)

def _extract_decadal_mean(nc_bytes, month_idx, decade_idx, is_sum=False):
    if nc_bytes is None: return None
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        data_vars = [v for v in ds.data_vars if v.lower() not in {c.lower() for c in ds.coords}]
        if not data_vars: ds.close(); os.unlink(tmp); return None
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'day' in d.lower()]
        if time_dims:
            n_days = da.sizes[time_dims[0]]
            start = decade_idx * 10
            end = min(start + 10, n_days)
            da = da.isel({time_dims[0]: slice(start, end)})
        val = float(da.sum().values) if is_sum else float(da.mean().values)
        ds.close(); os.unlink(tmp)
        return round(val, 1) if np.isfinite(val) else None
    except Exception:
        try: os.unlink(tmp)
        except: pass
        return None

# ══════════════════════════════════════════════════════════════════════════════
# RISK COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_pig_thi(T, RH):
    if T is None or RH is None: return None
    return round((1.8 * T + 32) - ((0.55 - 0.0055 * RH) * (1.8 * T - 26)), 1)

def thi_to_risk_pig(thi):
    if thi is None: return 0
    if thi < 75: return 1
    if thi <= 78: return 2
    return 3

def temp_to_risk_lua(T, stage):
    if T is None or stage not in LUA_TEMP_RISK: return 0
    cold_thresh, hot_thresh = LUA_TEMP_RISK[stage]
    if hot_thresh == 99: return 0
    if T < cold_thresh or T >= hot_thresh: return 3
    if T < cold_thresh + 2 or T >= hot_thresh - 3: return 2
    return 1

def rain_to_risk(R_sum, threshold_drought=20, threshold_flood=150):
    if R_sum is None: return 0
    if R_sum < threshold_drought or R_sum > threshold_flood: return 3
    if R_sum < threshold_drought + 20 or R_sum > threshold_flood - 50: return 2
    return 1

def compute_decade_risks(df_decadal):
    if df_decadal is None or df_decadal.empty: return {}
    risks = {crop: {} for crop in ["Lúa", "Bắp cải", "Súp lơ", "Dưa chuột", "Bí xanh", "Lợn", "Gà"]}

    for _, row in df_decadal.iterrows():
        decade = row["decade"]
        T = row.get("T2m")
        RH = row.get("RH2m", 75)
        R = row.get("R")

        # Rủi ro Lúa
        stage_lua = LUA_GROWTH_STAGES.get(decade, "")
        t_risk_lua = temp_to_risk_lua(T, stage_lua) if stage_lua else 0
        r_risk_lua = rain_to_risk(R) if stage_lua and stage_lua != "Nghỉ" else 0
        risks["Lúa"][decade] = max(t_risk_lua, r_risk_lua)

        # Rủi ro 4 loại Rau
        for crop_name, stages_dict, t_min, t_max in [
            ("Bắp cải", BAPCAI_GROWTH_STAGES, 10, 28),
            ("Súp lơ", SUPLO_GROWTH_STAGES, 10, 25),
            ("Dưa chuột", DUACHUOT_GROWTH_STAGES, 15, 35),
            ("Bí xanh", BIXANH_GROWTH_STAGES, 15, 35),
        ]:
            stage = stages_dict.get(decade, "")
            t_risk = 0
            if T is not None and stage and stage not in ["Nghỉ", "Làm đất", "Đất trống"]:
                if T > t_max + 2 or T < t_min - 2: t_risk = 3
                elif T > t_max or T < t_min: t_risk = 2
                else: t_risk = 1
            r_risk = rain_to_risk(R) if stage and stage not in ["Nghỉ", "Làm đất", "Đất trống"] else 0
            risks[crop_name][decade] = max(t_risk, r_risk)

        # Rủi ro Lợn
        thi = compute_pig_thi(T, RH if RH else 75)
        risks["Lợn"][decade] = thi_to_risk_pig(thi)

        # Rủi ro Gà
        t_risk_ga = 0
        if T is not None:
            if T > 35: t_risk_ga = 3
            elif T > 30 or T < 15: t_risk_ga = 2
            else: t_risk_ga = 1
        risks["Gà"][decade] = max(t_risk_ga, rain_to_risk(R, threshold_drought=10, threshold_flood=100))

    return risks

# ──────────────────────────────────────────────────────────────────────────────
# LỌC RAU THEO MÙA VỤ ("mùa nào rau nấy")
# ──────────────────────────────────────────────────────────────────────────────

VEGETABLE_GROWTH_STAGES = {
    "Bắp cải":   BAPCAI_GROWTH_STAGES,
    "Súp lơ":    SUPLO_GROWTH_STAGES,
    "Dưa chuột": DUACHUOT_GROWTH_STAGES,
    "Bí xanh":   BIXANH_GROWTH_STAGES,
}

# Các nhãn giai đoạn không tính là "đang canh tác" (đất trống / nghỉ vụ)
_OFF_SEASON_STAGES = {"Nghỉ", "Làm đất", "Đất trống", ""}

def get_active_crops(crops, active_decades):
    """
    Lọc danh sách cây trồng/vật nuôi theo MÙA VỤ – "mùa nào rau nấy".
    Với 4 loại rau (Bắp cải, Súp lơ, Dưa chuột, Bí xanh): chỉ giữ lại trong bản tin
    nếu có ít nhất 1 giai đoạn sinh trưởng thực sự (khác Nghỉ/Làm đất/Đất trống)
    rơi vào các kỳ thập (active_decades) của giai đoạn dự báo đang chọn.
    Ví dụ: Bắp cải chỉ trồng vụ Đông Xuân (T9 → T1) nên sẽ tự ẩn nếu kỳ dự báo
    rơi vào mùa hè, và tự hiện lại khi kỳ dự báo rơi vào mùa đông.
    Lúa, Lợn, Gà KHÔNG bị lọc theo cơ chế này (giữ nguyên hành vi cũ).

    Trả về: (danh_sach_dang_vao_vu, danh_sach_trai_vu_da_an)
    """
    active_crops, hidden_crops = [], []
    for crop in crops:
        stages = VEGETABLE_GROWTH_STAGES.get(crop)
        if stages is None:
            # Không phải 1 trong 4 loại rau theo mùa -> giữ nguyên, không lọc
            active_crops.append(crop)
            continue
        is_in_season = any(stages.get(d, "Nghỉ") not in _OFF_SEASON_STAGES for d in active_decades)
        if is_in_season:
            active_crops.append(crop)
        else:
            hidden_crops.append(crop)
    return active_crops, hidden_crops

# ══════════════════════════════════════════════════════════════════════════════
# CHART & TABLES
# ══════════════════════════════════════════════════════════════════════════════

def build_climate_normal_chart(commune_name, df_r, df_t, forecast_months):
    clim = get_commune_monthly_climate(commune_name, df_r, df_t)
    if not clim: return None
    months_vn = ["Th1","Th2","Th3","Th4","Th5","Th6","Th7","Th8","Th9","Th10","Th11","Th12"]
    R_vals = [clim.get(m, {}).get("R", 0) for m in range(1, 13)]
    T_vals = [clim.get(m, {}).get("T", 0) for m in range(1, 13)]
    bar_colors = ["#1565c0" if (m not in forecast_months) else "#e53935" for m in range(1, 13)]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=months_vn, y=R_vals, name="Lượng mưa", marker_color=bar_colors, yaxis="y1", hovertemplate="Mưa: %{y:.0f} mm<extra></extra>"))
    fig.add_trace(go.Scatter(x=months_vn, y=T_vals, name="Nhiệt độ", mode="lines+markers", line=dict(color="#e65100", width=2.5), marker=dict(color="#e65100", size=7), yaxis="y2", hovertemplate="Nhiệt độ: %{y:.1f}°C<extra></extra>"))
    fig.update_layout(
        title=dict(text="<b>Đặc trưng khí hậu trung bình nhiều năm (1981–2024)</b>", font=dict(size=13, family="Arial"), x=0.5, xanchor="center"),
        xaxis=dict(tickfont=dict(size=11), showgrid=False),
        yaxis=dict(title=dict(text="Lượng mưa (mm)", font=dict(color="#1565c0", size=11)), tickfont=dict(color="#1565c0", size=10), range=[0, max(R_vals) * 1.25 if R_vals else 400], showgrid=True, gridcolor="rgba(180,180,180,0.3)"),
        yaxis2=dict(title=dict(text="Nhiệt độ (°C)", font=dict(color="#e65100", size=11)), tickfont=dict(color="#e65100", size=10), overlaying="y", side="right", range=[min(T_vals) - 3, max(T_vals) + 5] if T_vals else [15, 40], showgrid=False),
        legend=dict(x=0.02, y=-0.15, orientation="h", bgcolor="rgba(255,255,255,0.8)", font=dict(size=11)),
        height=280, margin=dict(l=50, r=60, t=45, b=50), plot_bgcolor="white", paper_bgcolor="white", bargap=0.2,
    )
    return fig

def render_xacsuat_table(xacsuat_data, month_labels):
    def _fmt(v): return str(int(round(v))) if v is not None else "—"
    rows_T = ["Nhiệt độ trung bình nhiều năm (%)"]
    rows_R = ["Lượng mưa trung bình nhiều năm (%)"]
    for lbl in month_labels:
        probs = xacsuat_data.get(lbl, {})
        t_vals = probs.get("T", (None, None, None)); r_vals = probs.get("R", (None, None, None))
        rows_T.extend([_fmt(v) for v in t_vals]); rows_R.extend([_fmt(v) for v in r_vals])
    html = '<table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Arial;"><thead><tr style="background:#1e3a5f; color:white; text-align:center;"><th rowspan="2" style="border:1px solid #aaa; padding:4px 8px; width:140px;">Tháng</th>'
    for lbl in month_labels: html += f'<th colspan="3" style="border:1px solid #aaa; padding:4px 8px;">{lbl.replace("Tháng ","").split("/")[0]}</th>'
    html += "</tr><tr style='background:#2d6a4f; color:white; text-align:center;'>"
    for _ in month_labels: html += '<th style="border:1px solid #aaa; padding:4px 6px;">Thấp hơn<br><small>(XSHC)</small></th><th style="border:1px solid #aaa; padding:4px 6px;">Xấp xỉ<br><small>(XSCC)</small></th><th style="border:1px solid #aaa; padding:4px 6px;">Cao hơn<br><small>(XSVC)</small></th>'
    html += "</tr></thead><tbody>"
    for row_data, var_label in [(rows_T, "Nhiệt độ TB nhiều năm (%)"), (rows_R, "Lượng mưa TB nhiều năm (%)")]:
        html += f'<tr><td style="border:1px solid #aaa; padding:4px 8px; background:#e8f4f8; font-weight:bold;">{var_label}</td>'
        for val in row_data[1:]: html += f'<td style="border:1px solid #aaa; padding:4px 8px; text-align:center;">{val}</td>'
        html += "</tr>"
    html += "</tbody></table>"
    return html

def render_risk_table(crop_name, decades, decade_risks, growth_stages=None, diseases=None):
    risk_for_crop = decade_risks.get(crop_name, {})
    def _risk_cell(r):
        c = {0: "#f0f0f0", 1: "#c8f7c5", 2: "#fff176", 3: "#ff8a65"}.get(r, "#f0f0f0")
        t = {0: "—", 1: "Thấp", 2: "TB", 3: "Cao"}.get(r, "—")
        return f'<td style="border:1px solid #ccc; padding:3px 6px; text-align:center; background:{c}; font-weight:bold; font-size:12px;">{t}</td>'

    head_style = "border:1px solid #ccc; padding:4px 6px; text-align:center; background:#1e3a5f; color:white; font-size:12px;"
    row_style = "border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#f8f9fa;"
    
    html = f'<table style="border-collapse:collapse; width:100%; margin-bottom:12px;"><thead><tr><th style="{head_style} width:180px;">Giai đoạn</th>'
    for d in decades: html += f'<th style="{head_style} width:70px;">{d}</th>'
    html += '</tr>'
    
    if growth_stages:
        html += f'<tr><td style="border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#e3f2fd; font-weight:bold;">Chu kỳ sinh trưởng</td>'
        for d in decades: html += f'<td style="border:1px solid #ccc; padding:3px 4px; text-align:center; font-size:11px; background:#fff9e6;">{growth_stages.get(d, "")}</td>'
        html += '</tr>'
    html += f'</thead><tbody><tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px; background:#c5e1a5; font-weight:bold; font-size:12px;">Rủi ro khí hậu</td></tr>'

    climate_rows = [("Rủi ro nắng nóng / giá lạnh", risk_for_crop), ("Rủi ro mưa lớn", risk_for_crop)] if crop_name in ("Lợn", "Gà") else [("Rủi ro hạn hán", risk_for_crop), ("Rủi ro nắng nóng / giá lạnh", risk_for_crop), ("Rủi ro mưa lớn", risk_for_crop)]
    for row_label, row_risk in climate_rows:
        html += f'<tr><td style="{row_style} padding-left:16px;">{row_label}</td>'
        for d in decades: html += _risk_cell(row_risk.get(d, 0))
        html += '</tr>'

    if diseases:
        html += f'<tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px; background:#ffe082; font-weight:bold; font-size:12px;">Rủi ro sinh vật hại / dịch bệnh</td></tr>'
        for disease_name, disease_risk in diseases:
            html += f'<tr><td style="{row_style} padding-left:16px;">{disease_name}</td>'
            for d in decades: html += _risk_cell(disease_risk.get(d, 0))
            html += '</tr>'
    html += '</tbody></table>'
    return html

# ══════════════════════════════════════════════════════════════════════════════
# MAP RENDERING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _idw_knn(xi, yi, zi, query_xy, k=12, power=3.0, eps=1e-12):
    tree = cKDTree(np.column_stack([xi, yi]))
    dists, idxs = tree.query(query_xy, k=min(k, xi.size))
    if dists.ndim == 1: dists, idxs = dists[:, None], idxs[:, None]
    exact = dists <= eps
    out = np.empty(dists.shape[0], dtype=float)
    for r in np.where(exact.any(axis=1))[0]: out[r] = zi[idxs[r, np.where(exact[r])[0][0]]]
    rest = ~exact.any(axis=1)
    if np.any(rest):
        d, nn = dists[rest], idxs[rest]
        w = 1.0 / np.maximum(d, eps) ** power
        out[rest] = (w * zi[nn]).sum(axis=1) / w.sum(axis=1)
    return out

@st.cache_data(show_spinner=False)
def _compute_grid(lons_t, lats_t, vals_t, minx, miny, maxx, maxy, mask_wkt, GRID_N=400, SIGMA=1.0):
    xi, yi, zi = np.array(lons_t), np.array(lats_t), np.array(vals_t)
    gx_vec, gy_vec = np.linspace(minx, maxx, GRID_N), np.linspace(miny, maxy, GRID_N)
    gx, gy = np.meshgrid(gx_vec, gy_vec)
    gv = _idw_knn(xi, yi, zi, np.column_stack([gx.ravel(), gy.ravel()])).reshape(gx.shape)
    if SIGMA > 0: gv = gaussian_filter(gv, sigma=SIGMA)
    if mask_wkt:
        try:
            from shapely.vectorized import contains as shp_contains
            mask_flat = shp_contains(wkt_loads(mask_wkt), gx.ravel(), gy.ravel()).reshape(gx.shape)
        except (ImportError, AttributeError):
            prep_s = prep(wkt_loads(mask_wkt))
            mask_flat = np.array([prep_s.contains(Point(float(px), float(py))) for px, py in np.column_stack([gx.ravel(), gy.ravel()])], dtype=bool).reshape(gx.shape)
        gv = np.where(mask_flat, gv, np.nan)
    return gx_vec, gy_vec, gv

@st.cache_data(show_spinner=False)
def _mpl_to_plotly(cmap_name, n=128):
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap(cmap_name)
    pos = np.linspace(0, 1, n)
    return [[p, f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"] for p, (r, g, b, _) in zip(pos, [cmap(v) for v in pos])]

def build_figure(lons, lats, vals, meta, title, boundary_data, show_xa):
    bounds = boundary_data.get("bounds", (106.3, 20.6, 108.3, 21.8))
    minx, miny, maxx, maxy = bounds
    ok = ((lons >= minx - 1.5) & (lons <= maxx + 1.5) & (lats >= miny - 1.5) & (lats <= maxy + 1.5))
    xi, yi, zi = lons[ok], lats[ok], vals[ok]
    if xi.size == 0: return None, "Không có điểm dữ liệu trong vùng Quảng Ninh"

    gx_vec, gy_vec, gv_masked = _compute_grid(tuple(xi.tolist()), tuple(yi.tolist()), tuple(zi.tolist()), float(minx), float(miny), float(maxx), float(maxy), boundary_data.get("mask_wkt", ""))
    levels = sorted(meta.get("levels", list(range(-5, 6))))
    fig = go.Figure()

    if "tinh_x" in boundary_data:
        fig.add_trace(go.Scattergl(x=boundary_data["tinh_x"], y=boundary_data["tinh_y"], mode="lines", line=dict(color="#aab0b8", width=0.5), hoverinfo="skip", showlegend=False))
    
    fig.add_trace(go.Contour(
        z=np.where(np.isnan(gv_masked), np.nan, np.clip(gv_masked, levels[0], levels[-1])), x=gx_vec, y=gy_vec,
        colorscale=_mpl_to_plotly(meta.get("cmap", "RdBu_r")), zmin=levels[0], zmax=levels[-1], autocontour=False,
        contours=dict(start=levels[0], end=levels[-1], size=float(np.min(np.diff(levels))) if len(levels)>1 else 1.0, coloring="fill", showlines=False),
        colorbar=dict(title=dict(text=f"Chuẩn sai ({meta.get('unit', '')})", side="right", font=dict(size=12, family="Arial")), tickvals=levels, ticktext=[str(v) for v in levels], tickfont=dict(size=10), thickness=16, len=0.75, outlinewidth=1, outlinecolor="#aaa"),
        opacity=0.90, hovertemplate=f"Lon: %{{x:.3f}}°E<br>Lat: %{{y:.3f}}°N<br>Giá trị: %{{z:.2f}} {meta.get('unit', '')}<extra></extra>", name="Nội suy", showscale=True,
    ))

    if "qn_x" in boundary_data:
        fig.add_trace(go.Scattergl(x=boundary_data["qn_x"], y=boundary_data["qn_y"], mode="lines", line=dict(color="#111111", width=2.2), hoverinfo="skip", name="Ranh giới Quảng Ninh"))
    
    xa_visible = True if show_xa else "legendonly"
    if "xa_x" in boundary_data:
        fig.add_trace(go.Scattergl(x=boundary_data["xa_x"], y=boundary_data["xa_y"], mode="lines", line=dict(color="#e07b00", width=1.1, dash="dot"), hoverinfo="skip", visible=xa_visible, name="Ranh giới xã", legendgroup="xa_border"))
    if "xa_lx" in boundary_data and boundary_data["xa_texts"]:
        fig.add_trace(go.Scatter(x=boundary_data["xa_lx"], y=boundary_data["xa_ly"], mode="text", text=boundary_data["xa_texts"], textfont=dict(size=9, color="#111111"), textposition="middle center", hoverinfo="skip", visible=xa_visible, name="Tên xã", legendgroup="xa_label"))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, family="Arial"), x=0.5, xanchor="center"),
        xaxis=dict(title="Kinh độ (°E)", range=[minx-0.12, maxx+0.12], fixedrange=True, scaleanchor="y", scaleratio=1, constrain="domain", showgrid=True, gridcolor="rgba(180,180,180,0.3)"),
        yaxis=dict(title="Vĩ độ (°N)", range=[miny-0.12, maxy+0.12], fixedrange=True, showgrid=True, gridcolor="rgba(180,180,180,0.3)"),
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(255,255,255,0.85)", bordercolor="#aaa", borderwidth=1, font=dict(size=10)),
        margin=dict(l=60, r=20, t=50, b=50), height=680, plot_bgcolor="white", paper_bgcolor="white", hovermode="closest", dragmode=False,
        modebar_remove=["zoom","pan","zoomIn2d","zoomOut2d","resetScale2d","lasso2d","select2d","autoScale2d","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"],
    )
    return fig, None

def render_var_panel(var_prefix, meta, period, month_idx, boundary_data, month_labels, state_key, show_xa):
    with st.spinner(f"⏳ Đang tải {meta['label']} …"): nc_bytes = download_nc(period, var_prefix)
    if not nc_bytes: st.session_state[state_key] = {"error": f"Không tải được file NC: {var_prefix}.{period}.nc"}; return
    with st.spinner("🔄 Đang đọc dữ liệu …"): lons, lats, vals, err = load_nc_data(nc_bytes, month_idx)
    if err: st.session_state[state_key] = {"error": f"Lỗi đọc dữ liệu: {err}"}; return
    title = f"Chuẩn sai {meta['label']} – {month_labels[month_idx] if month_idx < len(month_labels) else f'Tháng +{month_idx+1}'} (Kỳ {period[:4]}/{period[4:]})"
    with st.spinner("🗺️ Đang nội suy và vẽ bản đồ …"): fig, err2 = build_figure(lons, lats, vals, meta, title, boundary_data, show_xa)
    if err2: st.session_state[state_key] = {"error": err2}; return
    st.session_state[state_key] = {"fig": fig, "filename": f"chuan_sai_{var_prefix.replace('.','_')}_{period}_t{month_idx+1}.png", "error": None}

def display_panel(state_key):
    result = st.session_state.get(state_key)
    if not result: return
    if result.get("error"): st.error(f"❌ {result['error']}"); return
    st.plotly_chart(result["fig"], use_container_width=True, config={"scrollZoom": False, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","zoomIn2d","zoomOut2d","autoScale2d","resetScale2d","lasso2d","select2d"], "toImageButtonOptions": {"format": "png", "filename": result["filename"], "scale": 2}})
    st.caption("💡 Hover vào bản đồ để xem giá trị. Bấm legend để ẩn/hiện lớp xã.")

@st.fragment
def _map_fragment(tab_key, var_dict, period, month_idx, boundary_data, month_labels, show_xa):
    state_key = f"map_{tab_key}"
    sel = st.selectbox("Chọn biến:", list(var_dict.keys()), format_func=lambda k: var_dict[k]["label"], key=f"sel_{tab_key}")
    if st.button("🗺️ Vẽ bản đồ", key=f"btn_{tab_key}", type="primary"): render_var_panel(sel, var_dict[sel], period, month_idx, boundary_data, month_labels, state_key, show_xa)
    display_panel(state_key)

def _geom_to_xy_list(gdf):
    all_x, all_y = [], []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty: continue
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            xs, ys = poly.exterior.xy
            all_x.extend(list(xs)); all_x.append(None)
            all_y.extend(list(ys)); all_y.append(None)
    return all_x, all_y

def build_commune_map_figure(commune_name, gdf_xa_all):
    col_key = COMMUNE_COL_MAP.get(commune_name)
    if not col_key: return None
    gdf_commune = load_commune_shp(col_key)
    if gdf_commune is None or gdf_commune.empty: return None

    fig = go.Figure()
    if gdf_xa_all is not None and not gdf_xa_all.empty:
        all_x, all_y = _geom_to_xy_list(gdf_xa_all)
        fig.add_trace(go.Scatter(x=all_x, y=all_y, mode="lines", line=dict(color="#cccccc", width=0.8), fill="toself", fillcolor="rgba(230,230,230,0.4)", hoverinfo="skip", showlegend=False))
    
    comm_x, comm_y = _geom_to_xy_list(gdf_commune)
    fig.add_trace(go.Scatter(x=comm_x, y=comm_y, mode="lines", fill="toself", fillcolor="rgba(30,58,95,0.40)", line=dict(color="#1e3a5f", width=2.5), hoverinfo="skip", showlegend=False))

    try:
        centroid = gdf_commune.geometry.unary_union.centroid
        fig.add_trace(go.Scatter(x=[centroid.x], y=[centroid.y], mode="markers+text", text=[commune_name], textposition="top center", textfont=dict(size=11, color="#1e3a5f", family="Arial"), marker=dict(size=9, color="#e53935", symbol="circle"), hoverinfo="skip", showlegend=False))
    except Exception: pass

    try:
        bounds = gdf_commune.total_bounds
        dx, dy = max((bounds[2] - bounds[0]) * 0.5, 0.05), max((bounds[3] - bounds[1]) * 0.5, 0.05)
        x_range, y_range = [bounds[0] - dx, bounds[2] + dx], [bounds[1] - dy, bounds[3] + dy]
    except Exception: x_range = y_range = None

    layout_kwargs = dict(height=230, margin=dict(l=5, r=5, t=5, b=5), plot_bgcolor="white", paper_bgcolor="white", dragmode=False, xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="y", scaleratio=1), yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    if x_range: layout_kwargs["xaxis"]["range"] = x_range; layout_kwargs["yaxis"]["range"] = y_range
    fig.update_layout(**layout_kwargs)
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# HTML EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def _fig_to_html_div(fig, div_id, export_height=None, export_width=None):
    if not fig: return ""
    try:
        fig = go.Figure(fig)  
        layout_update = {}
        if export_height: layout_update["height"] = export_height
        if export_width: layout_update["width"] = export_width; layout_update["autosize"] = False
        else: layout_update["autosize"] = True
        fig.update_layout(**layout_update)

        raw_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id, config={"displayModeBar": False, "responsive": True})
        m = re.search(r"(.*?)<script>(.*)</script>(.*)", raw_html, re.S)
        if not m: return raw_html
        return f"{m.group(1)}<script>(function() {{ function __renderWhenReady() {{ if (window.Plotly) {{ {m.group(2)} }} else {{ setTimeout(__renderWhenReady, 50); }} }} __renderWhenReady(); }})(); </script>{m.group(3)}"
    except Exception: return ""

def build_full_bulletin_html(commune_name, crops, period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa, active_decades, decade_risks, start_m, end_m, yr, mo):
    forecast_months = [((mo + offset - 1) % 12) + 1 for offset in range(1, 4)]
    map_div = _fig_to_html_div(build_commune_map_figure(commune_name, gdf_xa), "export_map_div", export_height=300, export_width=260)
    clim_div = _fig_to_html_div(build_climate_normal_chart(commune_name, df_r, df_t, forecast_months), "export_clim_div", export_height=300, export_width=680)

    xacsuat_html = render_xacsuat_table(xacsuat_data, month_labels) if xacsuat_data and any(xacsuat_data.values()) else "<p style='color:#888;'>ℹ️ Dữ liệu xác suất chưa có hoặc chưa tải được.</p>"

    risk_sections_html = ""
    emoji_map = {"Lúa": "🌾", "Bắp cải": "🥬", "Súp lơ": "🥦", "Dưa chuột": "🥒", "Bí xanh": "🍈", "Lợn": "🐷", "Gà": "🐔"}

    for crop in crops:
        emoji = emoji_map.get(crop, "🌿")
        gs, diseases = None, []

        if crop == "Lúa":
            gs = {d: LUA_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Rầy", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Sâu cuốn lá", {d: min(3, max(1, 2 if df_decadal is not None and not df_decadal.empty else 1)) for d in active_decades}),
                ("Đục thân", {d: 1 for d in active_decades}),
                ("Đạo ôn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Nấm cổ bông / Khô vằn", {d: 1 for d in active_decades}),
            ]
        elif crop == "Bắp cải":
            gs = {d: BAPCAI_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Sâu tơ / Bọ nhảy", {d: 1 for d in active_decades}),
                ("Sâu xanh", {d: 1 for d in active_decades}),
                ("Bệnh thối nhũn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Bệnh đốm vòng / Phấn trắng", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Súp lơ":
            gs = {d: SUPLO_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Sâu tơ / Bọ nhảy", {d: 1 for d in active_decades}),
                ("Sương mai", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Bệnh đốm trắng", {d: 1 for d in active_decades}),
            ]
        elif crop == "Dưa chuột":
            gs = {d: DUACHUOT_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Bọ cánh cứng / Bọ trĩ", {d: 1 for d in active_decades}),
                ("Sương mai", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Mốc trắng / Phấn trắng", {d: 1 for d in active_decades}),
                ("Thán thư", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Bí xanh":
            gs = {d: BIXANH_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Bọ cánh cứng", {d: 1 for d in active_decades}),
                ("Sâu non ăn lá, hoa", {d: 1 for d in active_decades}),
                ("Bệnh héo rũ", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Phấn trắng / Sương mai", {d: 1 for d in active_decades}),
            ]
        elif crop == "Lợn":
            gs = {d: LON_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Dịch tả / Lở mồm long móng", {d: 1 for d in active_decades}),
                ("Tai xanh / Suyễn lợn", {d: 1 for d in active_decades}),
                ("Tiêu chảy / Đóng dấu lợn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Tụ huyết trùng", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Gà":
            gs = {d: GA_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Cúm gia cầm / Hen gà", {d: 1 for d in active_decades}),
                ("Newcastle / Đậu gà", {d: 1 for d in active_decades}),
                ("Cầu trùng / Viêm ruột", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Ký sinh trùng đường máu", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]

        table_html = render_risk_table(crop, active_decades, decade_risks, gs, diseases)
        risk_sections_html += f"""
        <div class="risk-block">
          <div class="risk-header-export">{emoji} Mức độ rủi ro đối với {crop} giai đoạn {start_m} đến {end_m} năm {yr if mo + 3 <= 12 else yr+1}</div>
          {table_html}
          <div class="legend-export"><span class="legend-chip" style="background:#c8f7c5;">■ Thấp</span><span class="legend-chip" style="background:#fff176;">■ Trung bình (TB)</span><span class="legend-chip" style="background:#ff8a65;">■ Cao</span><span class="legend-chip" style="background:#f0f0f0;">■ Không áp dụng</span></div>
        </div>
        """

    plotly_cdn = "https://cdn.plot.ly/plotly-2.32.0.min.js"
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Bản tin khí hậu – Xã {commune_name} – {start_m} đến {end_m}</title><script src="{plotly_cdn}"></script>
<style>
  html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; color-adjust: exact; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 0; padding: 0; background: #f4f6f8; color: #222; }}
  .page {{ max-width: 1100px; margin: 18px auto 60px auto; background: #fff; box-shadow: 0 2px 14px rgba(0,0,0,0.10); border-radius: 10px; overflow: hidden; }}
  .doc-header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%); color: #fff; padding: 22px 28px 18px 28px; }}
  .doc-header .org {{ font-size: 12.5px; opacity: 0.9; margin: 0 0 4px 0; }}
  .doc-header h1 {{ margin: 4px 0 6px 0; font-size: 1.5rem; }}
  .doc-header .meta {{ font-size: 12.5px; opacity: 0.9; }}
  .toolbar {{ display: flex; justify-content: flex-end; gap: 10px; padding: 12px 28px; background: #eef3f6; border-bottom: 1px solid #dbe3e8; }}
  .btn {{ border: none; border-radius: 6px; padding: 9px 18px; font-size: 13.5px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }}
  .btn-print {{ background: #1e3a5f; color: #fff; }} .btn-print:hover {{ background: #16314f; }}
  .content {{ padding: 24px 28px 10px 28px; }}
  .info-row {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 18px; }}
  .info-card {{ flex: 1; min-width: 180px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; }}
  .info-card .label {{ font-size: 11.5px; color: #667085; margin-bottom: 2px; }}
  .info-card .value {{ font-size: 14.5px; font-weight: 700; color: #1e3a5f; }}
  .two-col {{ display: flex; gap: 18px; margin-bottom: 22px; flex-wrap: nowrap; align-items: flex-start; }}
  .col-map {{ flex: 0 0 260px; width: 260px; display: flex; flex-direction: column; }}
  .col-chart {{ flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; }}
  .section-title {{ font-size: 1rem; font-weight: 700; color: #1e3a5f; margin: 0 0 8px 0; display: flex; align-items: center; gap: 6px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #fcfdfe; }}
  .card-chart {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px; background: #fcfdfe; height: 314px; overflow: hidden; display: flex; align-items: center; justify-content: center; }}
  .card-chart > div {{ width: 100%; height: 100%; }}
  hr.sep {{ border: none; border-top: 1px solid #e2e8f0; margin: 22px 0; }}
  .risk-block {{ margin-bottom: 22px; }}
  .risk-header-export {{ background: linear-gradient(135deg, #7b2d00 0%, #c0392b 100%); color: #fff; padding: 8px 16px; border-radius: 6px; font-size: 1rem; font-weight: 700; margin: 0 0 6px 0; }}
  .legend-export {{ font-size: 11.5px; margin: -4px 0 4px 0; }}
  .legend-chip {{ padding: 2px 9px; margin-right: 6px; border-radius: 3px; }}
  table {{ font-family: inherit; }}
  .footer-note {{ font-size: 11.5px; color: #8a93a3; text-align: center; padding: 16px 0 22px 0; }}
  @media print {{
    * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }}
    body {{ background: #fff; }} .page {{ box-shadow: none; margin: 0; border-radius: 0; max-width: 100%; }}
    .toolbar {{ display: none !important; }} .risk-block {{ break-inside: avoid; page-break-inside: avoid; }}
    .two-col {{ break-inside: avoid; page-break-inside: avoid; display: flex !important; flex-wrap: nowrap !important; }}
    .col-map  {{ flex: 0 0 260px !important; width: 260px !important; }} .col-chart {{ flex: 1 1 0 !important; min-width: 0 !important; }}
    .card-chart {{ height: 314px !important; overflow: hidden !important; }} .info-row {{ break-inside: avoid; }}
  }}
</style>
</head><body>
  <div class="page">
    <div class="doc-header">
      <p class="org">Viện Khoa học Khí tượng Thủy văn Môi trường và Biển — Phòng Nghiên cứu Khí tượng nông nghiệp và Dịch vụ khí hậu</p>
      <h1>📋 Bản tin cảnh báo rủi ro khí hậu – Xã {commune_name}</h1>
      <div class="meta">Giai đoạn dự báo: tháng {start_m} đến tháng {end_m} &nbsp;•&nbsp; Kỳ dữ liệu: {period[:4]}/{period[4:]} &nbsp;•&nbsp; Xuất lúc: {datetime.now().strftime("%H:%M %d/%m/%Y")}</div>
    </div>
    <div class="toolbar"><button class="btn btn-print" onclick="window.print()">🖨️ In / Lưu PDF</button></div>
    <div class="content">
      <div class="info-row">
        <div class="info-card"><div class="label">🏘️ Xã</div><div class="value">{commune_name}</div></div>
        <div class="info-card"><div class="label">🌱 Đối tượng nông nghiệp đang vào vụ</div><div class="value">{", ".join(crops) if crops else "—"}</div></div>
        <div class="info-card"><div class="label">📅 Kỳ dự báo</div><div class="value">{month_labels[0]} → {month_labels[-1]}</div></div>
      </div>
      <div class="two-col">
        <div class="col-map"><div class="section-title">📍 Vị trí xã</div><div class="card-chart">{map_div if map_div else "<p style='color:#888;'>Không có dữ liệu bản đồ.</p>"}</div></div>
        <div class="col-chart"><div class="section-title">📈 Đặc trưng khí hậu TBNN (1981–2024)</div><div class="card-chart">{clim_div if clim_div else "<p style='color:#888;'>Không có dữ liệu biểu đồ.</p>"}</div></div>
      </div>
      <div class="section-title">📊 Dự báo khí hậu xác suất</div><div class="card" style="overflow-x:auto;">{xacsuat_html}</div>
      <hr class="sep">{risk_sections_html}
    </div>
    <div class="footer-note">Bản tin được tạo tự động từ hệ thống Bản tin Khí hậu Quảng Ninh — phiên bản 1.3.8</div>
  </div>
</body></html>"""

def render_export_button(commune_name, crops, period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa, active_decades, decade_risks, start_m, end_m, yr, mo, button_key):
    if st.button("📤 Export bản tin", key=button_key, type="primary", use_container_width=False):
        with st.spinner("📄 Đang tạo bản tin HTML …"):
            html_doc = build_full_bulletin_html(commune_name, crops, period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa, active_decades, decade_risks, start_m, end_m, yr, mo)
        b64 = base64.b64encode(html_doc.encode("utf-8")).decode("ascii")
        components.html(f"""<script>(function() {{ const b64 = "{b64}"; const byteChars = atob(b64); const byteNumbers = new Array(byteChars.length); for (let i = 0; i < byteChars.length; i++) {{ byteNumbers[i] = byteChars.charCodeAt(i); }} const byteArray = new Uint8Array(byteNumbers); const blob = new Blob([byteArray], {{type: 'text/html;charset=utf-8'}}); const url = URL.createObjectURL(blob); window.open(url, '_blank'); }})();</script>""", height=0)
        st.success("✅ Đã mở bản tin trong tab mới. Nếu trình duyệt chặn pop-up, vui lòng cho phép pop-up cho trang này rồi bấm lại.")

# ══════════════════════════════════════════════════════════════════════════════
# RENDER BẢN TIN XÃ
# ══════════════════════════════════════════════════════════════════════════════

def render_commune_bulletin(commune_name, crops, period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa=None):
    yr, mo = int(period[:4]), int(period[4:])
    forecast_months = [((mo + offset - 1) % 12) + 1 for offset in range(1, 4)]
    
    active_decades = []
    for offset in range(1, 4):
        m2 = ((mo + offset - 1) % 12) + 1
        for d in ["T1", "T2", "T3"]: active_decades.append(f"{d}/{m2}")

    decade_risks = compute_decade_risks(df_decadal)
    start_m = month_labels[0].replace("Tháng ", ""); end_m = month_labels[-1].replace("Tháng ", "")
    
    st.markdown(f'<div class="commune-title">📋 Bản tin cảnh báo khí hậu tháng {start_m} đến {end_m} – Xã {commune_name}</div>', unsafe_allow_html=True)
    col_map, col_chart = st.columns([1, 2])

    with col_map:
        st.markdown("**📍 Vị trí xã**")
        with st.spinner("🗺️ Đang tải bản đồ xã …"): fig_map = build_commune_map_figure(commune_name, gdf_xa)
        if fig_map: st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})
        else: st.info(f"Xã **{commune_name}**")

    with col_chart:
        fig_clim = build_climate_normal_chart(commune_name, df_r, df_t, forecast_months)
        if fig_clim: st.plotly_chart(fig_clim, use_container_width=True, config={"displayModeBar": False})
        else: st.info("⚠️ Chưa tải được dữ liệu TBNN cho xã này.")

    st.markdown("**📊 Dự báo khí hậu xác suất**")
    if xacsuat_data and any(xacsuat_data.values()):
        st.markdown(render_xacsuat_table(xacsuat_data, month_labels), unsafe_allow_html=True)
    else:
        tbl_data = {"Biến": ["Nhiệt độ TB nhiều năm (%)", "Lượng mưa TB nhiều năm (%)"]}
        for lbl in month_labels:
            m = lbl.replace("Tháng ","").split("/")[0]
            tbl_data.update({f"Tháng {m} – Thấp hơn (XSHC)": ["—", "—"], f"Tháng {m} – Xấp xỉ (XSCC)": ["—", "—"], f"Tháng {m} – Cao hơn (XSVC)": ["—", "—"]})
        st.info("ℹ️ Dữ liệu xác suất chưa có hoặc chưa tải được – bảng hiển thị giá trị chờ.")
        st.dataframe(pd.DataFrame(tbl_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown(f"**🌱 Đối tượng nông nghiệp:** {', '.join(crops) if crops else '—'}")

    emoji_map = {"Lúa": "🌾", "Bắp cải": "🥬", "Súp lơ": "🥦", "Dưa chuột": "🥒", "Bí xanh": "🍈", "Lợn": "🐷", "Gà": "🐔"}

    for crop in crops:
        emoji = emoji_map.get(crop, "🌿")
        st.markdown(f'<div class="risk-header">{emoji} Mức độ rủi ro đối với {crop} giai đoạn {start_m} đến {end_m} năm {yr if mo + 3 <= 12 else yr+1}</div>', unsafe_allow_html=True)
        
        gs, diseases = None, []
        if crop == "Lúa":
            gs = {d: LUA_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Rầy", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Sâu cuốn lá", {d: min(3, max(1, 2 if df_decadal is not None and not df_decadal.empty else 1)) for d in active_decades}),
                ("Đục thân", {d: 1 for d in active_decades}),
                ("Đạo ôn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Nấm cổ bông / Khô vằn", {d: 1 for d in active_decades}),
            ]
        elif crop == "Bắp cải":
            gs = {d: BAPCAI_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Sâu tơ / Bọ nhảy", {d: 1 for d in active_decades}),
                ("Sâu xanh", {d: 1 for d in active_decades}),
                ("Bệnh thối nhũn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Bệnh đốm vòng / Phấn trắng", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Súp lơ":
            gs = {d: SUPLO_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Sâu tơ / Bọ nhảy", {d: 1 for d in active_decades}),
                ("Sương mai", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Bệnh đốm trắng", {d: 1 for d in active_decades}),
            ]
        elif crop == "Dưa chuột":
            gs = {d: DUACHUOT_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Bọ cánh cứng / Bọ trĩ", {d: 1 for d in active_decades}),
                ("Sương mai", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Mốc trắng / Phấn trắng", {d: 1 for d in active_decades}),
                ("Thán thư", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Bí xanh":
            gs = {d: BIXANH_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Bọ cánh cứng", {d: 1 for d in active_decades}),
                ("Sâu non ăn lá, hoa", {d: 1 for d in active_decades}),
                ("Bệnh héo rũ", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Phấn trắng / Sương mai", {d: 1 for d in active_decades}),
            ]
        elif crop == "Lợn":
            gs = {d: LON_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Dịch tả / Lở mồm long móng", {d: 1 for d in active_decades}),
                ("Tai xanh / Suyễn lợn", {d: 1 for d in active_decades}),
                ("Tiêu chảy / Đóng dấu lợn", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Tụ huyết trùng", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Gà":
            gs = {d: GA_GROWTH_STAGES.get(d, "") for d in active_decades}
            diseases = [
                ("Cúm gia cầm / Hen gà", {d: 1 for d in active_decades}),
                ("Newcastle / Đậu gà", {d: 1 for d in active_decades}),
                ("Cầu trùng / Viêm ruột", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
                ("Ký sinh trùng đường máu", {d: min(3, decade_risks.get(crop, {}).get(d, 1)) for d in active_decades}),
            ]

        st.markdown(render_risk_table(crop, active_decades, decade_risks, gs, diseases), unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px; margin:-6px 0 10px 0;"><span style="background:#c8f7c5; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Thấp</span><span style="background:#fff176; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Trung bình (TB)</span><span style="background:#ff8a65; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Cao</span><span style="background:#f0f0f0; padding:2px 8px; border-radius:3px;">■ Không áp dụng</span></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CÁC TRANG CHÍNH
# ══════════════════════════════════════════════════════════════════════════════

def page_tong_quan():
    # ── Header: logo Viện + tên Viện liên kết tới Cổng TTĐT Sở KH&CN tỉnh Quảng Ninh ──
    if INSTITUTE_LOGO_URL:
        logo_html = f'<img src="{INSTITUTE_LOGO_URL}" alt="Logo Viện">'
    else:
        logo_html = '<div class="org-logo-fallback">🏛️</div>'
    st.markdown(f"""
    <div class="org-header">
        {logo_html}
        <div class="org-text">
            <a href="{DOST_QUANGNINH_URL}" target="_blank" rel="noopener noreferrer">{INSTITUTE_NAME}</a>
            <div class="org-sub">Liên kết chuyên môn với Sở Khoa học và Công nghệ tỉnh Quảng Ninh</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Banner ảnh nền Quảng Ninh ──
    st.markdown(f"""
    <div class="hero-banner" style="background-image:url('{TONGQUAN_BG_URL}');">
        <div class="hero-content">
            <h1>🌾 Công cụ quản lý rủi ro khí hậu đối với cây trồng và vật nuôi tỉnh Quảng Ninh</h1>
            <p>Hệ thống hỗ trợ tạo <b>bản tin cảnh báo khí hậu</b> cho các xã tại Quảng Ninh, bao gồm đánh giá rủi ro cho <b>Lúa, Bắp cải, Súp lơ, Dưa chuột, Bí xanh, Lợn, Gà</b> theo từng kỳ tháng.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏘️ Số xã", str(len(COMMUNE_CROPS)))
    c2.metric("🌱 Cây trồng / Vật nuôi", "7")
    c3.metric("📅 Kỳ dự báo", "3 tháng")
    c4.metric("📄 Bản tin đã tạo", "0")

def page_du_bao():
    st.markdown('<div class="module-header">🔄 Dự báo khí hậu mùa</div>', unsafe_allow_html=True)
    with st.spinner("⏳ Đang tải shapefile …"): gdf_all_tinh, gdf_tinh_qn, gdf_xa = load_shapefiles()
    if gdf_all_tinh is None and gdf_xa is None: st.warning("⚠️ Không tải được shapefile – bản đồ sẽ không có ranh giới.")
    boundary_data = build_boundary_traces_cached(gdf_all_tinh, gdf_tinh_qn, gdf_xa)

    with st.spinner("🔍 Kiểm tra dữ liệu mới nhất …"): periods = fetch_available_periods()
    if not periods: st.error("❌ Không kết nối được server hoặc chưa có dữ liệu."); return

    periods_desc = list(reversed(periods)); yr_mo_labels = [f"{p[:4]}/{p[4:]}" for p in periods_desc]
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sel_idx = st.selectbox("📅 Kỳ dự báo:", range(len(periods_desc)), format_func=lambda i: yr_mo_labels[i], help="Tự động cập nhật khi server có thư mục mới")
        sel_period = periods_desc[sel_idx]

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = [f"Tháng {((mo + d - 1) % 12) + 1:02d}/{yr + (mo + d - 1) // 12}" for d in range(1, 4)]
    with col2: month_idx = st.selectbox("🗓️ Hạn dự báo:", range(3), format_func=lambda i: month_labels[i])
    with col3: show_xa = st.toggle("🗺️ Hiển thị lớp xã", value=False)

    st.markdown("---")
    tab_c, tab_e = st.tabs(["🌡️ Chuẩn sai dự báo khí hậu", "⚠️ Chuẩn sai dự báo cực đoan"])
    with tab_c: _map_fragment("c", CLIMATE_VARS, sel_period, month_idx, boundary_data, month_labels, show_xa)
    with tab_e: _map_fragment("e", EXTREME_VARS, sel_period, month_idx, boundary_data, month_labels, show_xa)

def page_ban_tin_xa():
    st.markdown('<div class="module-header">📋 Bản tin cảnh báo rủi ro khí hậu</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([2, 3])

    with col1:
        with st.spinner("🔍 Kiểm tra dữ liệu …"): periods = fetch_available_periods()
        if not periods: st.error("❌ Không kết nối được server."); return
        periods_desc = list(reversed(periods))
        sel_period = periods_desc[st.selectbox("📅 Kỳ dự báo:", range(len(periods_desc)), format_func=lambda i: f"{periods_desc[i][:4]}/{periods_desc[i][4:]}")]
        sel_commune = st.selectbox("🏘️ Chọn xã:", list(COMMUNE_CROPS.keys()))

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = [f"Tháng {((mo + d - 1) % 12) + 1:02d}/{yr + (mo + d - 1) // 12}" for d in range(1, 4)]
    crops = COMMUNE_CROPS.get(sel_commune, [])

    with st.spinner("📥 Đang tải dữ liệu ERA5 TBNN …"): df_r, df_t = load_era5_data()
    with st.spinner("📥 Đang tải dự báo theo thập …"): df_decadal = load_member_decadal(sel_period)
    with st.spinner("📍 Đang tải tọa độ xã …"): lon_c, lat_c = get_commune_lonlat(sel_commune, load_commune_lonlat())
    if lon_c is None or lat_c is None: st.warning(f"⚠️ Không tìm thấy tọa độ cho xã **{sel_commune}** trong file `lon_lat_quangninh.xlsx` – bảng xác suất sẽ hiển thị giá trị chờ.")
    with st.spinner("📥 Đang tải dự báo xác suất …"): xacsuat_data = load_xacsuat_for_commune(sel_period, sel_commune, lon_c, lat_c)
    with st.spinner("⏳ Đang tải shapefile nền …"): _, _, gdf_xa = load_shapefiles()

    active_decades = [f"{d}/{((mo + offset - 1) % 12) + 1}" for offset in range(1, 4) for d in ["T1", "T2", "T3"]]
    decade_risks = compute_decade_risks(df_decadal)
    start_m, end_m = month_labels[0].replace("Tháng ", ""), month_labels[-1].replace("Tháng ", "")

    # 🌱 Mùa nào rau nấy: tự động ẩn rau trái vụ, hiện rau đang vào vụ theo kỳ dự báo
    crops, crops_hidden = get_active_crops(crops, active_decades)

    with col2:
        st.markdown("**📅 Kỳ dự báo:**")
        st.info(f"Tháng {month_labels[0].split('Tháng ')[1]} → {month_labels[-1].split('Tháng ')[1]}")
        sub_label, sub_btn = st.columns([3, 1.4])
        with sub_label:
            st.markdown(f"**🌾 Đối tượng đang vào vụ:** {', '.join(crops) if crops else '—'}")
            if crops_hidden:
                st.caption(f"🍂 Trái vụ (đã tự ẩn): {', '.join(crops_hidden)}")
        with sub_btn:
            render_export_button(
                sel_commune, crops, sel_period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa,
                active_decades, decade_risks, start_m, end_m, yr, mo, button_key="export_bulletin_btn",
            )
    st.markdown("---")
    render_commune_bulletin(sel_commune, crops, sel_period, month_labels, df_r, df_t, df_decadal, xacsuat_data, gdf_xa)

def page_ban_tin_da_luu():
    st.markdown('<div class="module-header">💾 Bản tin đã lưu</div>', unsafe_allow_html=True); st.info("Module đang phát triển.")
def page_export():
    st.markdown('<div class="module-header">📤 Export bản tin</div>', unsafe_allow_html=True); st.info("Module đang phát triển.")
def page_phan_hoi():
    st.markdown('<div class="module-header">💬 Phản hồi</div>', unsafe_allow_html=True); st.info("Module đang phát triển.")

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🌾 Bản tin Khí hậu\n**Quảng Ninh – Nông nghiệp**\n---")
    menu = st.radio("📌 Chọn module:", ["🏠 Tổng quan", "🔄 Dự báo khí hậu mùa", "📋 Bản tin cảnh báo rủi ro khí hậu", "💾 Bản tin đã lưu", "📤 Export bản tin", "💬 Phản hồi"], label_visibility="collapsed")
    st.markdown("---\nPhòng Nghiên cứu Khí tượng nông nghiệp và Dịch vụ khí hậu\nViện Khoa học Khí tượng Thủy văn Môi trường và Biển\n---\n*Phiên bản 1.3.9 – 06/2026*")

if   menu == "🏠 Tổng quan":                        page_tong_quan()
elif menu == "🔄 Dự báo khí hậu mùa":                page_du_bao()
elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":   page_ban_tin_xa()
elif menu == "💾 Bản tin đã lưu":                      page_ban_tin_da_luu()
elif menu == "📤 Export bản tin":                      page_export()
elif menu == "💬 Phản hồi":                            page_phan_hoi()
