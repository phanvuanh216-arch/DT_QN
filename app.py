# -*- coding: utf-8 -*-
"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
THAY ĐỔI v1.4.0 – MODULE BẢN TIN CẢNH BÁO RỦI RO KHÍ HẬU:
  [NEW]  Xuất PDF bản tin xã dùng ReportLab + font DejaVu (hỗ trợ tiếng Việt)
  [KEEP] Giữ nguyên toàn bộ tính năng v1.3.0
"""

import streamlit as st
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
    .pdf-export-box {
        background: linear-gradient(135deg, #e8f5e9 0%, #e3f2fd 100%);
        border: 1.5px solid #2d6a4f; border-radius: 10px;
        padding: 14px 20px; margin: 12px 0 18px 0;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL        = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
XACSUAT_URL     = "http://222.254.32.10/forecast/Detai_QuangNinh/xacsuat/domain_d02/"
MEMBER_URL      = "http://222.254.32.10/forecast/Detai_QuangNinh/trungbinhmember/domain_d02/"
SHP_QN_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"
ERA5_R_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/R_ERA5_CDFT_corrected.xlsx"
ERA5_T_URL      = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/T2m_ERA5_QM_corrected.xlsx"
ECOLOGY_URL     = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/B%E1%BA%A3ng%20sinh%20th%C3%A1i%20v%C3%A0%20m%C3%B9a%20v%E1%BB%A5_19-6.xlsx"

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
    "ano.SU35":   {"label": "Số ngày nắng nóng >=35°C (SU35)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-10, 12, 2))},
    "ano.SU37":   {"label": "Số ngày nắng nóng >=37°C (SU37)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-8, 10, 2))},
    "ano.SU39":   {"label": "Số ngày nắng nóng >=39°C (SU39)", "unit": "ngày", "cmap": "RdYlBu_r", "levels": list(range(-6, 8, 2))},
    "ano.Evap":   {"label": "Bốc hơi (Evap)",                 "unit": "mm",   "cmap": "BrBG",     "levels": [-100,-50,-25,-10,0,10,25,50,100]},
}

# Danh sách xã và đối tượng nông nghiệp
COMMUNE_CROPS = {
    "Hải Sơn":    ["Lợn"],
    "Hải Ninh":   ["Lợn"],
    "Móng Cái 1": ["Lợn"],
    "Móng Cái 2": ["Lợn"],
    "Móng Cái 3": ["Lợn"],
    "Quảng Hà":   ["Lúa", "Rau", "Lợn", "Gà"],
    "Đường Hoa":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Quảng Đức":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Cái Chiên":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Quảng Tân":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Đầm Hà":     ["Lúa", "Rau", "Lợn", "Gà"],
    "Hải Hòa":    ["Rau", "Gà"],
    "Tiên Yên":   ["Rau", "Gà"],
    "Điền Xá":    ["Rau", "Gà"],
    "Đông Ngũ":   ["Rau", "Gà"],
    "Hải Lạng":   ["Rau", "Gà"],
    "Đông Mai":   ["Lúa", "Rau", "Lợn", "Gà"],
    "Hiệp Hòa":   ["Lúa", "Rau", "Lợn", "Gà"],
    "Quang Yên":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Hà An":      ["Lúa", "Rau", "Lợn", "Gà"],
    "Phong Cốc":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Liên Hòa":   ["Lúa", "Rau", "Lợn", "Gà"],
    "Yên Tử":     ["Rau", "Lợn", "Gà"],
    "Vàng Danh":  ["Rau", "Lợn", "Gà"],
    "Uông Bí":    ["Rau", "Lợn", "Gà"],
    "An Sinh":    ["Lúa", "Rau", "Lợn", "Gà"],
    "Đông Triều": ["Lúa", "Rau", "Lợn", "Gà"],
    "Bình Khuê":  ["Lúa", "Rau", "Lợn", "Gà"],
    "Mạo Khê":    ["Lúa", "Rau", "Lợn", "Gà"],
    "Hoàng Quế":  ["Lúa", "Rau", "Lợn", "Gà"],
}

# Map commune name → column key in ERA5 files
COMMUNE_COL_MAP = {
    "Hải Sơn":    "haison",
    "Hải Ninh":   "haininh",
    "Móng Cái 1": "mongcai1",
    "Móng Cái 2": "mongcai2",
    "Móng Cái 3": "mongcai3",
    "Quảng Hà":   "quangha",
    "Đường Hoa":  "duonghoa",
    "Quảng Đức":  "quangduc",
    "Cái Chiên":  "caichien",
    "Quảng Tân":  "quangtan",
    "Đầm Hà":     "damha",
    "Hải Hòa":    "haihoa",
    "Tiên Yên":   "tienyen",
    "Điền Xá":    "dienxa",
    "Đông Ngũ":   "dongngu",
    "Hải Lạng":   "hailang",
    "Đông Mai":   "dongmai",
    "Hiệp Hòa":   "hiephoa",
    "Quang Yên":  "quangyen",
    "Hà An":      "haan",
    "Phong Cốc":  "phongcoc",
    "Liên Hòa":   "lienhoa",
    "Yên Tử":     "yentu",
    "Vàng Danh":  "vangdanh",
    "Uông Bí":    "uongbi",
    "An Sinh":    "ansinh",
    "Đông Triều": "dongtrieu",
    "Bình Khuê":  "binhkhe",
    "Mạo Khê":    "maokhe",
    "Hoàng Quế":  "hoangque",
}

LUA_GROWTH_STAGES = {
    "T1/6": "Gieo, nay mam",
    "T2/6": "Gieo, nay mam",
    "T3/6": "Ma",
    "T1/7": "Ma",
    "T2/7": "De nhanh",
    "T3/7": "De nhanh",
    "T1/8": "Lam dong",
    "T2/8": "Phan hoa hoa",
    "T3/8": "Tro - thu phan",
}

# Vietnamese display labels for growth stages
LUA_GROWTH_STAGES_VN = {
    "T1/6": "Gieo, nảy mầm",
    "T2/6": "Gieo, nảy mầm",
    "T3/6": "Mạ",
    "T1/7": "Mạ",
    "T2/7": "Đẻ nhánh",
    "T3/7": "Đẻ nhánh",
    "T1/8": "Làm đòng",
    "T2/8": "Phân hóa hoa",
    "T3/8": "Trỗ – thụ phấn",
}

RAU_GROWTH_STAGES = {
    "T1/6": "Thân lá (Bí xanh)",
    "T2/6": "Ra hoa (Bí xanh)",
    "T3/6": "Ra hoa – Đậu quả (Dưa chuột)",
    "T1/7": "Nảy mầm (Dưa chuột)",
    "T2/7": "Cây con (Dưa chuột)",
    "T3/7": "Sinh trưởng thân lá",
    "T1/8": "Ra hoa – Đậu quả",
    "T2/8": "Ra hoa – Đậu quả",
    "T3/8": "Thu hoạch",
}

LUA_TEMP_RISK = {
    "Gieo, nay mam": (10, 45),
    "Ma":             (12, 35),
    "De nhanh":       (9,  33),
    "Lam dong":       (15, 38),
    "Phan hoa hoa":   (15, 38),
    "Tro - thu phan": (22, 38),
}

PIG_THI_RISK = {"normal": 74, "warn": 78, "danger": 83, "critical": 84}
CHICKEN_THI_RISK = {"normal": 70, "warn": 75, "danger": 81, "critical": 81}

RISK_LABELS = {0: "—", 1: "Thấp", 2: "Trung bình", 3: "Cao"}
RISK_COLORS = {0: "#f0f0f0", 1: "#c8f7c5", 2: "#fff176", 3: "#ff8a65"}

DECADAL_LABELS = ["T1/6","T2/6","T3/6","T1/7","T2/7","T3/7","T1/8","T2/8","T3/8"]

# Font paths for ReportLab (Vietnamese support via DejaVu)
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


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
# LOAD SHAPEFILE
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
                        qn_mask = gdf_all[col].str.contains(
                            "Quảng Ninh|Quang Ninh", case=False, na=False)
                        break
                    elif cu in ("MATINH", "MA_TINH", "TINH_CD", "PROVCODE", "MA"):
                        try:
                            qn_mask = gdf_all[col].astype(str).str.strip() == "22"
                        except Exception:
                            pass
                        break
                if qn_mask is not None and qn_mask.any():
                    gdf_tinh_qn = gdf_all[qn_mask].copy()
    except Exception:
        pass

    try:
        p = _download_shp("xa_quangninh")
        if p:
            gdf_xa = _read_safe(p)
    except Exception:
        pass

    return gdf_all_tinh, gdf_tinh_qn, gdf_xa


@st.cache_resource(show_spinner=False)
def build_boundary_traces_cached(_gdf_all_tinh, _gdf_tinh_qn, _gdf_xa):
    def _geom_to_xy(gdf):
        all_x, all_y = [], []
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                continue
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
            except Exception:
                pass
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


# ══════════════════════════════════════════════════════════════════════════════
# ERA5 CLIMATE DATA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def load_era5_data():
    try:
        r_r = requests.get(ERA5_R_URL, timeout=30)
        r_t = requests.get(ERA5_T_URL, timeout=30)
        if r_r.status_code != 200 or r_t.status_code != 200:
            return None, None

        df_r = pd.read_excel(io.BytesIO(r_r.content), sheet_name=0, header=None)
        df_t = pd.read_excel(io.BytesIO(r_t.content), sheet_name=0, header=None)

        cols_r = df_r.iloc[0].tolist()
        df_r.columns = cols_r
        df_r = df_r.iloc[3:].copy()
        df_r = df_r.rename(columns={"year": "year", "month": "month", "day": "day"})
        for c in ["year", "month", "day"]:
            df_r[c] = pd.to_numeric(df_r[c], errors="coerce")
        df_r = df_r.dropna(subset=["year", "month", "day"])
        df_r[["year","month","day"]] = df_r[["year","month","day"]].astype(int)

        cols_t = df_t.iloc[0].tolist()
        df_t.columns = cols_t
        df_t = df_t.iloc[3:].copy()
        for c in ["year", "month", "day"]:
            df_t[c] = pd.to_numeric(df_t[c], errors="coerce")
        df_t = df_t.dropna(subset=["year", "month", "day"])
        df_t[["year","month","day"]] = df_t[["year","month","day"]].astype(int)

        return df_r, df_t
    except Exception:
        return None, None


def get_commune_monthly_climate(commune_name, df_r, df_t):
    col_key = COMMUNE_COL_MAP.get(commune_name)
    if col_key is None or df_r is None or df_t is None:
        return {}

    mask_r = (df_r["year"] >= 1989) & (df_r["year"] <= 2018)
    mask_t = (df_t["year"] >= 1989) & (df_t["year"] <= 2018)

    r_col = None
    t_col = None
    for c in df_r.columns:
        if str(c).lower().strip() == col_key.lower():
            r_col = c; break
    for c in df_t.columns:
        if str(c).lower().strip() == col_key.lower():
            t_col = c; break

    if r_col is None or t_col is None:
        return {}

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


# ══════════════════════════════════════════════════════════════════════════════
# NETCDF DATA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_available_periods() -> list:
    try:
        resp = requests.get(BASE_URL, timeout=10)
        resp.raise_for_status()
        return sorted(set(re.findall(r'(\d{6})/', resp.text)))
    except Exception as e:
        st.warning(f"Khong the lay danh sach thu muc: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def download_nc(period: str, var_prefix: str, base_url: str = None):
    if base_url is None:
        base_url = BASE_URL
    url = f"{base_url}{period}/{var_prefix}.{period}.nc"
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.status_code == 200 else None
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_nc_data(nc_bytes: bytes, month_idx: int):
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        coord_names = {c.lower() for c in ds.coords}
        data_vars = [v for v in ds.data_vars if v.lower() not in coord_names]
        if not data_vars:
            return None, None, None, "Khong tim thay bien du lieu"
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'month' in d.lower()]
        if time_dims:
            da = da.isel({time_dims[0]: min(month_idx, da.sizes[time_dims[0]] - 1)})
        lat_names = [d for d in da.dims if 'lat' in d.lower() or d == 'y']
        lon_names = [d for d in da.dims if 'lon' in d.lower() or d == 'x']
        if not lat_names or not lon_names:
            return None, None, None, "Khong tim thay chieu lat/lon"
        lats, lons = da[lat_names[0]].values, da[lon_names[0]].values
        vals = da.values
        if lons.ndim == 1:
            lons, lats = np.meshgrid(lons, lats)
        flat_lon, flat_lat, flat_val = lons.ravel(), lats.ravel(), vals.ravel()
        ok = np.isfinite(flat_val) & (np.abs(flat_val) < 1e10)
        ds.close(); os.unlink(tmp)
        return flat_lon[ok], flat_lat[ok], flat_val[ok], None
    except Exception as e:
        try: os.unlink(tmp)
        except: pass
        return None, None, None, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# PROBABILITY DATA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_xacsuat_periods() -> list:
    try:
        resp = requests.get(XACSUAT_URL, timeout=10)
        resp.raise_for_status()
        return sorted(set(re.findall(r'(\d{6})/', resp.text)))
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def load_xacsuat_for_commune(period: str, commune_name: str, month_offsets=(1,2,3)):
    result = {}
    yr, mo = int(period[:4]), int(period[4:])

    for offset in month_offsets:
        m2 = mo + offset
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        label = f"Thang {m2:02d}/{y2}"

        t_bytes = download_nc(period, "xacsuat.T2m", XACSUAT_URL)
        r_bytes = download_nc(period, "xacsuat.R", XACSUAT_URL)

        t_prob = _extract_prob_at_commune(t_bytes, offset - 1) if t_bytes else None
        r_prob = _extract_prob_at_commune(r_bytes, offset - 1) if r_bytes else None

        result[label] = {
            "T": t_prob if t_prob else (None, None, None),
            "R": r_prob if r_prob else (None, None, None),
        }

    return result


def _extract_prob_at_commune(nc_bytes, month_idx):
    if nc_bytes is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        data_vars = [v for v in ds.data_vars]
        if not data_vars:
            ds.close(); os.unlink(tmp); return None
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'month' in d.lower()]
        cat_dims = [d for d in da.dims if 'cat' in d.lower() or 'class' in d.lower() or 'prob' in d.lower()]
        vals = []
        if len(data_vars) >= 3:
            for var in data_vars[:3]:
                da_v = ds[var]
                if time_dims:
                    da_v = da_v.isel({time_dims[0]: min(month_idx, da_v.sizes[time_dims[0]] - 1)})
                vals.append(float(da_v.mean().values))
        elif cat_dims:
            for i in range(3):
                da_v = da.isel({cat_dims[0]: i})
                if time_dims:
                    da_v = da_v.isel({time_dims[0]: min(month_idx, da_v.sizes[time_dims[0]] - 1)})
                vals.append(float(da_v.mean().values))
        else:
            ds.close(); os.unlink(tmp); return None
        ds.close(); os.unlink(tmp)
        if len(vals) == 3:
            total = sum(vals) if sum(vals) > 0 else 1
            return tuple(round(v/total*100) for v in vals)
        return None
    except Exception:
        try: os.unlink(tmp)
        except: pass
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER DATA
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_member_decadal(period: str, month_offsets=(1,2,3)):
    yr, mo = int(period[:4]), int(period[4:])
    rows = []

    for offset in month_offsets:
        m2 = mo + offset
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1

        for decade_idx, decade_label in enumerate(["T1", "T2", "T3"]):
            label = f"{decade_label}/{m2}"
            t_bytes = download_nc(period, "T2m", MEMBER_URL)
            rh_bytes = download_nc(period, "RH2m", MEMBER_URL)
            r_bytes = download_nc(period, "R", MEMBER_URL)

            t_val = _extract_decadal_mean(t_bytes, offset - 1, decade_idx, is_sum=False)
            rh_val = _extract_decadal_mean(rh_bytes, offset - 1, decade_idx, is_sum=False)
            r_val = _extract_decadal_mean(r_bytes, offset - 1, decade_idx, is_sum=True)

            rows.append({"decade": label, "T2m": t_val, "RH2m": rh_val, "R": r_val})

    return pd.DataFrame(rows)


def _extract_decadal_mean(nc_bytes, month_idx, decade_idx, is_sum=False):
    if nc_bytes is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        data_vars = [v for v in ds.data_vars if v.lower() not in {c.lower() for c in ds.coords}]
        if not data_vars:
            ds.close(); os.unlink(tmp); return None
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'day' in d.lower()]
        if time_dims:
            n_days = da.sizes[time_dims[0]]
            start = decade_idx * 10
            end = min(start + 10, n_days)
            da = da.isel({time_dims[0]: slice(start, end)})
        if is_sum:
            val = float(da.sum().values)
        else:
            val = float(da.mean().values)
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
    if T is None or RH is None:
        return None
    thi = (1.8 * T + 32) - ((0.55 - 0.0055 * RH) * (1.8 * T - 26))
    return round(thi, 1)


def thi_to_risk_pig(thi):
    if thi is None:
        return 0
    if thi < 75:
        return 1
    if thi <= 78:
        return 2
    if thi <= 83:
        return 3
    return 3


def temp_to_risk_lua(T, stage):
    if T is None or stage not in LUA_TEMP_RISK:
        return 0
    cold_thresh, hot_thresh = LUA_TEMP_RISK[stage]
    if T < cold_thresh:
        return 3
    if T >= hot_thresh:
        return 3
    if T < cold_thresh + 2 or T >= hot_thresh - 3:
        return 2
    return 1


def rain_to_risk(R_sum, threshold_drought=20, threshold_flood=150):
    if R_sum is None:
        return 0
    if R_sum < threshold_drought:
        return 3
    if R_sum > threshold_flood:
        return 3
    if R_sum < threshold_drought + 20 or R_sum > threshold_flood - 50:
        return 2
    return 1


def compute_decade_risks(df_decadal):
    if df_decadal is None or df_decadal.empty:
        return {}

    risks = {crop: {} for crop in ["Lua", "Rau", "Lon", "Ga"]}
    # Map to internal keys
    crop_map = {"Lua": "Lúa", "Rau": "Rau", "Lon": "Lợn", "Ga": "Gà"}

    risks_vn = {crop: {} for crop in ["Lúa", "Rau", "Lợn", "Gà"]}

    for _, row in df_decadal.iterrows():
        decade = row["decade"]
        T = row.get("T2m")
        RH = row.get("RH2m", 75)
        R = row.get("R")

        stage = LUA_GROWTH_STAGES.get(decade, "")
        t_risk = temp_to_risk_lua(T, stage) if stage else 0
        r_risk = rain_to_risk(R)
        risks_vn["Lúa"][decade] = max(t_risk, r_risk)

        t_risk_rau = 0
        if T is not None:
            if T > 38 or T < 10:
                t_risk_rau = 3
            elif T > 35 or T < 15:
                t_risk_rau = 2
            else:
                t_risk_rau = 1
        risks_vn["Rau"][decade] = max(t_risk_rau, rain_to_risk(R))

        thi = compute_pig_thi(T, RH if RH else 75)
        risks_vn["Lợn"][decade] = thi_to_risk_pig(thi)

        t_risk_ga = 0
        if T is not None:
            if T > 35:
                t_risk_ga = 3
            elif T > 30:
                t_risk_ga = 2
            elif T < 15:
                t_risk_ga = 2
            else:
                t_risk_ga = 1
        risks_vn["Gà"][decade] = max(t_risk_ga, rain_to_risk(R, threshold_drought=10, threshold_flood=100))

    return risks_vn


# ══════════════════════════════════════════════════════════════════════════════
# CHART: TBNN
# ══════════════════════════════════════════════════════════════════════════════

def build_climate_normal_chart(commune_name, df_r, df_t, forecast_months):
    clim = get_commune_monthly_climate(commune_name, df_r, df_t)
    if not clim:
        return None

    months_vn = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    R_vals = [clim.get(m, {}).get("R", 0) for m in range(1, 13)]
    T_vals = [clim.get(m, {}).get("T", 0) for m in range(1, 13)]

    bar_colors = ["#1565c0" if (m not in forecast_months) else "#e53935" for m in range(1, 13)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months_vn, y=R_vals,
        name="Rainfall",
        marker_color=bar_colors,
        yaxis="y1",
        hovertemplate="Mua: %{y:.0f} mm<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months_vn, y=T_vals,
        name="Temperature",
        mode="lines+markers",
        line=dict(color="#e65100", width=2.5),
        marker=dict(color="#e65100", size=7, symbol="circle"),
        yaxis="y2",
        hovertemplate="Nhiet do: %{y:.1f}C<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text="<b>Climate Trend of Past Normal Years (1989-2018)</b>",
            font=dict(size=13, family="Arial"), x=0.5, xanchor="center",
        ),
        xaxis=dict(tickfont=dict(size=11), showgrid=False),
        yaxis=dict(
            title=dict(text="Rainfall (mm)", font=dict(color="#1565c0", size=11)),
            tickfont=dict(color="#1565c0", size=10),
            range=[0, max(R_vals) * 1.25 if R_vals else 400],
            showgrid=True, gridcolor="rgba(180,180,180,0.3)",
        ),
        yaxis2=dict(
            title=dict(text="Temperature (C)", font=dict(color="#e65100", size=11)),
            tickfont=dict(color="#e65100", size=10),
            overlaying="y", side="right",
            range=[min(T_vals) - 3, max(T_vals) + 5] if T_vals else [15, 40],
            showgrid=False,
        ),
        legend=dict(x=0.02, y=-0.15, orientation="h",
                    bgcolor="rgba(255,255,255,0.8)", font=dict(size=11)),
        height=280,
        margin=dict(l=50, r=60, t=45, b=50),
        plot_bgcolor="white", paper_bgcolor="white", bargap=0.2,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# PROBABILITY TABLE HTML
# ══════════════════════════════════════════════════════════════════════════════

def render_xacsuat_table(xacsuat_data, month_labels):
    def _fmt(v):
        return str(int(round(v))) if v is not None else "—"

    n_months = len(month_labels)
    html = """
    <table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Arial;">
      <thead>
        <tr style="background:#1e3a5f; color:white; text-align:center;">
          <th rowspan="2" style="border:1px solid #aaa; padding:4px 8px; width:140px;">Thang</th>
    """
    for lbl in month_labels:
        m = lbl.replace("Thang ","").split("/")[0]
        html += f'<th colspan="3" style="border:1px solid #aaa; padding:4px 8px;">{m}</th>'
    html += "</tr><tr style='background:#2d6a4f; color:white; text-align:center;'>"
    for _ in month_labels:
        html += '<th style="border:1px solid #aaa; padding:4px 6px;">Thap hon<br><small>(XSHC)</small></th>'
        html += '<th style="border:1px solid #aaa; padding:4px 6px;">Xap xi<br><small>(XSCC)</small></th>'
        html += '<th style="border:1px solid #aaa; padding:4px 6px;">Cao hon<br><small>(XSVC)</small></th>'
    html += "</tr></thead><tbody>"

    rows_T, rows_R = [], []
    for lbl in month_labels:
        probs = xacsuat_data.get(lbl, {})
        t_vals = probs.get("T", (None, None, None))
        r_vals = probs.get("R", (None, None, None))
        rows_T.extend([_fmt(v) for v in t_vals])
        rows_R.extend([_fmt(v) for v in r_vals])

    for row_data, var_label in [(rows_T, "Nhiet do TB nhieu nam (%)"),
                                 (rows_R, "Luong mua TB nhieu nam (mm)")]:
        html += f'<tr><td style="border:1px solid #aaa; padding:4px 8px; background:#e8f4f8; font-weight:bold;">{var_label}</td>'
        for val in row_data:
            html += f'<td style="border:1px solid #aaa; padding:4px 8px; text-align:center;">{val}</td>'
        html += "</tr>"

    html += "</tbody></table>"
    return html


# ══════════════════════════════════════════════════════════════════════════════
# RISK TABLE HTML
# ══════════════════════════════════════════════════════════════════════════════

def render_risk_table(crop_name, decades, decade_risks, growth_stages=None, diseases=None):
    risk_for_crop = decade_risks.get(crop_name, {})
    RISK_COLOR = {0: "#f0f0f0", 1: "#c8f7c5", 2: "#fff176", 3: "#ff8a65"}
    RISK_TEXT  = {0: "—", 1: "Thap", 2: "TB", 3: "Cao"}

    def _risk_cell(r):
        c = RISK_COLOR.get(r, "#f0f0f0")
        t = RISK_TEXT.get(r, "—")
        return f'<td style="border:1px solid #ccc; padding:3px 6px; text-align:center; background:{c}; font-weight:bold; font-size:12px;">{t}</td>'

    head_style = "border:1px solid #ccc; padding:4px 6px; text-align:center; background:#1e3a5f; color:white; font-size:12px;"
    row_style = "border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#f8f9fa;"
    group_style = "border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#e3f2fd; font-weight:bold;"

    html = '<table style="border-collapse:collapse; width:100%; margin-bottom:12px;">'
    html += '<thead><tr>'
    html += f'<th style="{head_style} width:180px;">Giai doan</th>'
    for d in decades:
        html += f'<th style="{head_style} width:70px;">{d}</th>'
    html += '</tr>'

    if growth_stages:
        html += '<tr>'
        html += f'<td style="{group_style}">Chu ky sinh truong</td>'
        for d in decades:
            stage = growth_stages.get(d, "")
            html += f'<td style="border:1px solid #ccc; padding:3px 4px; text-align:center; font-size:11px; background:#fff9e6;">{stage}</td>'
        html += '</tr>'
    html += '</thead><tbody>'

    html += f'<tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px; background:#c5e1a5; font-weight:bold; font-size:12px;">Rui ro khi hau</td></tr>'

    if crop_name in ("Lon", "Ga", "Lợn", "Gà"):
        climate_rows = [("Rui ro nang nong / gia lanh", risk_for_crop),
                        ("Rui ro mua lon", risk_for_crop)]
    else:
        climate_rows = [("Rui ro han han", risk_for_crop),
                        ("Rui ro nang nong / gia lanh", risk_for_crop),
                        ("Rui ro mua lon", risk_for_crop)]

    for row_label, row_risk in climate_rows:
        html += '<tr>'
        html += f'<td style="{row_style} padding-left:16px;">{row_label}</td>'
        for d in decades:
            html += _risk_cell(row_risk.get(d, 0))
        html += '</tr>'

    if diseases:
        html += f'<tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px; background:#ffe082; font-weight:bold; font-size:12px;">Rui ro sinh vat hai / dich benh</td></tr>'
        for disease_name, disease_risk in diseases:
            html += '<tr>'
            html += f'<td style="{row_style} padding-left:16px;">{disease_name}</td>'
            for d in decades:
                html += _risk_cell(disease_risk.get(d, 0))
            html += '</tr>'

    html += '</tbody></table>'
    return html


# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT – REPORTLAB
# ══════════════════════════════════════════════════════════════════════════════

def _get_disease_list(crop_name, active_decades, decade_risks):
    """Return list of (disease_name, {decade: risk}) for a crop."""
    if crop_name == "Lúa":
        return [
            ("Ray", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
            ("Sau cuon la", {d: min(3, max(1, 2)) for d in active_decades}),
            ("Duc than", {d: 1 for d in active_decades}),
            ("Dao on", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
            ("Nam co bong", {d: 1 for d in active_decades}),
            ("Kho van", {d: 1 for d in active_decades}),
            ("Ray nau", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
        ]
    elif crop_name == "Rau":
        return [
            ("Sau xanh", {d: 1 for d in active_decades}),
            ("Sau to", {d: 1 for d in active_decades}),
            ("Rep", {d: 1 for d in active_decades}),
            ("Bo nhay", {d: 1 for d in active_decades}),
            ("Benh thoi goc", {d: min(3, decade_risks.get("Rau", {}).get(d, 1)) for d in active_decades}),
            ("Suong mai", {d: min(3, decade_risks.get("Rau", {}).get(d, 1)) for d in active_decades}),
        ]
    elif crop_name == "Lợn":
        return [
            ("Dich ta lon Chau Phi", {d: 1 for d in active_decades}),
            ("Dich ta lon co dien", {d: 1 for d in active_decades}),
            ("Viem phoi dinh suon", {d: 1 for d in active_decades}),
            ("Suyen lon", {d: 1 for d in active_decades}),
            ("Tai xanh (PRRS)", {d: 1 for d in active_decades}),
            ("Tieu chay do E.coli", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
            ("Dong dau lon", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
            ("Lo mom long mong", {d: 1 for d in active_decades}),
            ("Tu huyet trung lon", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
        ]
    else:  # Gà
        return [
            ("Hen ga", {d: 1 for d in active_decades}),
            ("Cum gia cam DLC cao", {d: 1 for d in active_decades}),
            ("Cau trung ga", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
            ("Viem ruot hoai tu", {d: 1 for d in active_decades}),
            ("Newcastle", {d: 1 for d in active_decades}),
            ("Tu huyet trung gia cam", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
            ("Ky sinh trung duong mau", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
            ("Dau ga", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
        ]


def generate_bulletin_pdf(
    commune_name: str,
    crops: list,
    period: str,
    month_labels: list,
    df_r, df_t,
    df_decadal,
    xacsuat_data,
) -> bytes:
    """
    Generate a PDF bulletin for a commune.
    Returns raw PDF bytes.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    # ── Register fonts ──
    pdfmetrics.registerFont(TTFont("DVSans", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("DVSans-Bold", FONT_BOLD))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    # ── Styles ──
    S = getSampleStyleSheet()
    def _style(name, font="DVSans", size=10, leading=14, align=TA_LEFT,
                color=colors.black, bold=False, space_before=0, space_after=2):
        return ParagraphStyle(
            name, fontName="DVSans-Bold" if bold else font,
            fontSize=size, leading=leading, alignment=align,
            textColor=color, spaceBefore=space_before, spaceAfter=space_after,
        )

    st_title   = _style("title",    size=14, leading=18, align=TA_CENTER, bold=True,
                         color=colors.HexColor("#1e3a5f"), space_before=4, space_after=6)
    st_sub     = _style("sub",      size=11, leading=15, align=TA_CENTER,
                         color=colors.HexColor("#2d6a4f"), space_before=0, space_after=4)
    st_meta    = _style("meta",     size=9,  leading=13, align=TA_CENTER,
                         color=colors.HexColor("#555555"), space_after=8)
    st_section = _style("section",  size=11, leading=14, bold=True,
                         color=colors.white, space_before=8, space_after=4)
    st_body    = _style("body",     size=9,  leading=13, space_after=2)
    st_label   = _style("label",    size=8,  leading=12, bold=True,
                         color=colors.HexColor("#333333"))
    st_caption = _style("caption",  size=7.5, leading=11,
                         color=colors.HexColor("#666666"), space_before=0, space_after=4)

    # ── Colors ──
    COL_HEADER   = colors.HexColor("#1e3a5f")
    COL_SUBHEADER = colors.HexColor("#2d6a4f")
    COL_RISK1    = colors.HexColor("#c8f7c5")
    COL_RISK2    = colors.HexColor("#fff176")
    COL_RISK3    = colors.HexColor("#ff8a65")
    COL_RISK0    = colors.HexColor("#f0f0f0")
    COL_GROWTH   = colors.HexColor("#fff9e6")
    COL_CLIMATE_ROW = colors.HexColor("#c5e1a5")
    COL_DISEASE_ROW = colors.HexColor("#ffe082")
    COL_TABLEROW1 = colors.HexColor("#f8f9fa")
    COL_XACSUAT  = colors.HexColor("#e8f4f8")

    RISK_CELL_COLOR = {0: COL_RISK0, 1: COL_RISK1, 2: COL_RISK2, 3: COL_RISK3}
    RISK_CELL_TEXT  = {0: "-", 1: "Thap", 2: "TB", 3: "Cao"}

    # ── Derived info ──
    yr, mo = int(period[:4]), int(period[4:])
    forecast_months = []
    for offset in range(1, 4):
        m2 = mo + offset
        m2 = ((m2 - 1) % 12) + 1
        forecast_months.append(m2)

    active_decades = []
    for offset in range(1, 4):
        m2 = mo + offset
        m2 = ((m2 - 1) % 12) + 1
        for d in ["T1", "T2", "T3"]:
            active_decades.append(f"{d}/{m2}")

    start_m = month_labels[0].replace("Thang ", "")
    end_m   = month_labels[-1].replace("Thang ", "")

    decade_risks = compute_decade_risks(df_decadal)
    clim = get_commune_monthly_climate(commune_name, df_r, df_t)

    story = []

    # ════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════
    story.append(Paragraph(
        "BAN TIN CANH BAO RUI RO KHI HAU NONG NGHIEP",
        st_title
    ))
    story.append(Paragraph(
        f"Xa {commune_name}  |  Thang {start_m} den {end_m}",
        st_sub
    ))
    story.append(Paragraph(
        f"Ky du bao: {period[:4]}/{period[4:]}   |   "
        f"Doi tuong: {', '.join(crops)}   |   "
        f"Ngay xuat: {datetime.now().strftime('%d/%m/%Y')}",
        st_meta
    ))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=COL_HEADER, spaceAfter=6))

    # ════════════════════════════════════════════════════════
    # 1. TBNN CLIMATE TABLE (12 months)
    # ════════════════════════════════════════════════════════
    if clim:
        # Section header row
        story.append(_section_header_para("1. Dieu kien khi hau trung binh nhieu nam (TBNN) 1989-2018",
                                           COL_HEADER, st_section))

        months_short = ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"]
        R_vals = [clim.get(m, {}).get("R", 0) for m in range(1, 13)]
        T_vals = [clim.get(m, {}).get("T", 0) for m in range(1, 13)]

        # Highlight forecast months with bold
        def _month_cell(m_idx):
            m_num = m_idx + 1
            bold = m_num in forecast_months
            txt = months_short[m_idx]
            if bold:
                return Paragraph(f"<b>{txt}*</b>", _style(f"mc{m_idx}", size=8, leading=10,
                                                            align=TA_CENTER, bold=True,
                                                            color=colors.HexColor("#b71c1c")))
            return Paragraph(txt, _style(f"mc{m_idx}", size=8, leading=10, align=TA_CENTER))

        def _num_cell(val, fmt="{:.1f}", bold_months=None, m_idx=None):
            txt = fmt.format(val) if val is not None else "-"
            bold = (bold_months is not None and m_idx is not None and (m_idx+1) in bold_months)
            s = _style(f"nc{m_idx}", size=8, leading=10, align=TA_CENTER,
                        bold=bold, color=colors.HexColor("#b71c1c") if bold else colors.black)
            return Paragraph(txt, s)

        col_w = [2.8*cm] + [1.02*cm] * 12
        tbnn_data = [
            [Paragraph("Chi so", _style("ch0", size=8, bold=True, align=TA_LEFT))] +
            [_month_cell(i) for i in range(12)],

            [Paragraph("Nhiet do TB (C)", _style("ch1", size=8, bold=True))] +
            [_num_cell(T_vals[i], "{:.1f}", forecast_months, i) for i in range(12)],

            [Paragraph("Luong mua (mm)", _style("ch2", size=8, bold=True))] +
            [_num_cell(R_vals[i], "{:.0f}", forecast_months, i) for i in range(12)],
        ]

        tbnn_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COL_HEADER),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (0, -1), COL_XACSUAT),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
            ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ])
        # Highlight forecast month columns
        for m_num in forecast_months:
            col_idx = m_num  # columns: 0=label, 1=T1, ..., 12=T12
            tbnn_style.add("BACKGROUND", (col_idx, 1), (col_idx, -1),
                           colors.HexColor("#fff3e0"))

        tbnn_table = Table(tbnn_data, colWidths=col_w)
        tbnn_table.setStyle(tbnn_style)
        story.append(tbnn_table)
        story.append(Paragraph("(*) Cac thang du bao duoc danh dau do", st_caption))
        story.append(Spacer(1, 0.3*cm))

    # ════════════════════════════════════════════════════════
    # 2. PROBABILITY FORECAST TABLE
    # ════════════════════════════════════════════════════════
    story.append(_section_header_para("2. Du bao khi hau xac suat",
                                       COL_SUBHEADER, st_section))

    if xacsuat_data and any(xacsuat_data.values()):
        n_months = len(month_labels)
        # Build header rows
        xs_header1 = [Paragraph("Bien", _style("xs_h1", size=8, bold=True, align=TA_CENTER,
                                                 color=colors.white))]
        xs_header2 = [Paragraph("", _style("xs_h2", size=8))]
        for lbl in month_labels:
            m_str = lbl.replace("Thang ", "")
            xs_header1 += [
                Paragraph(f"Thang {m_str.split('/')[0]}", _style("xsh1a", size=8, bold=True,
                                                                   align=TA_CENTER, color=colors.white)),
                Paragraph("", _style("xsh1b", size=8)),
                Paragraph("", _style("xsh1c", size=8)),
            ]
            xs_header2 += [
                Paragraph("Thap hon\n(XSHC)", _style("xsh2a", size=7, align=TA_CENTER, color=colors.white)),
                Paragraph("Xap xi\n(XSCC)",   _style("xsh2b", size=7, align=TA_CENTER, color=colors.white)),
                Paragraph("Cao hon\n(XSVC)",   _style("xsh2c", size=7, align=TA_CENTER, color=colors.white)),
            ]

        def _xs_row(label, key):
            row = [Paragraph(label, _style("xsrl", size=8, bold=True))]
            for lbl in month_labels:
                probs = xacsuat_data.get(lbl, {}).get(key, (None, None, None))
                for v in probs:
                    txt = str(int(round(v))) if v is not None else "-"
                    row.append(Paragraph(txt, _style("xsrv", size=8, align=TA_CENTER)))
            return row

        xs_data = [
            xs_header1, xs_header2,
            _xs_row("Nhiet do TB nhieu nam (%)", "T"),
            _xs_row("Luong mua TB nhieu nam (mm)", "R"),
        ]

        n_prob_cols = n_months * 3
        xs_col_w = [3.5*cm] + [1.5*cm] * n_prob_cols
        xs_table = Table(xs_data, colWidths=xs_col_w)

        xs_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 1), COL_SUBHEADER),
            ("TEXTCOLOR",  (0, 0), (-1, 1), colors.white),
            ("SPAN", (0, 0), (0, 1)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
            ("ROWBACKGROUNDS", (1, 2), (-1, -1), [COL_XACSUAT, colors.white]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (1, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
        # Span month headers
        for i, _ in enumerate(month_labels):
            col_start = 1 + i * 3
            xs_style.add("SPAN", (col_start, 0), (col_start + 2, 0))

        xs_table.setStyle(xs_style)
        story.append(xs_table)
    else:
        story.append(Paragraph("Du lieu xac suat chua co hoac chua tai duoc.",
                                _style("xs_na", size=9, color=colors.HexColor("#888888"))))

    story.append(Spacer(1, 0.3*cm))

    # ════════════════════════════════════════════════════════
    # 3. RISK TABLES PER CROP
    # ════════════════════════════════════════════════════════
    story.append(_section_header_para(
        f"3. Muc do rui ro nong nghiep thang {start_m} den {end_m}",
        COL_HEADER, st_section
    ))

    for crop in crops:
        emoji_text = {"Lúa": "[Lua]", "Rau": "[Rau]", "Lợn": "[Lon]", "Gà": "[Ga]"}.get(crop, f"[{crop}]")
        crop_year = yr if mo + 3 <= 12 else yr + 1

        story.append(Spacer(1, 0.2*cm))
        # Crop sub-header
        crop_header = Table(
            [[Paragraph(f"{emoji_text}  Rui ro doi voi {crop}  –  Thang {start_m} den {end_m} nam {crop_year}",
                        _style("ch_crop", size=10, bold=True, color=colors.white, align=TA_LEFT))]],
            colWidths=["100%"],
        )
        crop_header.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#c0392b")),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",  (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(crop_header)
        story.append(Spacer(1, 0.15*cm))

        # ── Build risk table ──
        growth_stages = None
        if crop == "Lúa":
            growth_stages = {d: LUA_GROWTH_STAGES_VN.get(d, "") for d in active_decades}
        elif crop == "Rau":
            growth_stages = {d: RAU_GROWTH_STAGES.get(d, "") for d in active_decades}

        diseases = _get_disease_list(crop, active_decades, decade_risks)
        risk_for_crop = decade_risks.get(crop, {})

        # Column widths: label col + one col per decade
        n_dec = len(active_decades)
        dec_col_w = 1.55 * cm
        label_col_w = doc.width - n_dec * dec_col_w
        col_widths = [label_col_w] + [dec_col_w] * n_dec

        def _hdr_para(txt):
            return Paragraph(txt, _style("th", size=7.5, bold=True,
                                          align=TA_CENTER, color=colors.white))

        def _risk_para(r):
            return Paragraph(RISK_CELL_TEXT[r],
                             _style("rp", size=8, bold=True, align=TA_CENTER))

        def _label_para(txt, indent=0):
            return Paragraph(("  " * indent) + txt,
                             _style("lp", size=8, leading=11))

        def _section_para(txt, bg_key="climate"):
            return Paragraph(txt, _style("sp", size=8, bold=True))

        # Header row
        header_row = [_hdr_para("Giai doan / Chi tieu")] + [_hdr_para(d) for d in active_decades]
        table_data = [header_row]

        table_style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), COL_HEADER),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING",   (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ]

        row_idx = 1

        # Growth stage row
        if growth_stages:
            gs_row = [_label_para("Chu ky sinh truong", 0)] + [
                Paragraph(growth_stages.get(d, ""), _style(f"gs{i}", size=7, align=TA_CENTER,
                                                            color=colors.HexColor("#555")))
                for i, d in enumerate(active_decades)
            ]
            table_data.append(gs_row)
            table_style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), COL_GROWTH))
            row_idx += 1

        # Climate risk section header
        table_data.append(
            [Paragraph("Rui ro khi hau", _style("cls", size=8, bold=True))] +
            [""] * n_dec
        )
        table_style_cmds.append(("SPAN", (0, row_idx), (-1, row_idx)))
        table_style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), COL_CLIMATE_ROW))
        row_idx += 1

        if crop in ("Lợn", "Gà"):
            climate_risk_rows = [("Rui ro nang nong / gia lanh", risk_for_crop),
                                  ("Rui ro mua lon", risk_for_crop)]
        else:
            climate_risk_rows = [("Rui ro han han", risk_for_crop),
                                  ("Rui ro nang nong / gia lanh", risk_for_crop),
                                  ("Rui ro mua lon", risk_for_crop)]

        for cr_label, cr_risk in climate_risk_rows:
            row = [_label_para(cr_label, 1)] + [_risk_para(cr_risk.get(d, 0)) for d in active_decades]
            table_data.append(row)
            bg = COL_TABLEROW1 if row_idx % 2 == 0 else colors.white
            table_style_cmds.append(("BACKGROUND", (0, row_idx), (0, row_idx), colors.HexColor("#f0f0f0")))
            for col_i, d in enumerate(active_decades):
                r_val = cr_risk.get(d, 0)
                table_style_cmds.append(
                    ("BACKGROUND", (col_i + 1, row_idx), (col_i + 1, row_idx), RISK_CELL_COLOR[r_val])
                )
            row_idx += 1

        # Disease section header
        table_data.append(
            [Paragraph("Rui ro sinh vat hai / dich benh", _style("dsh", size=8, bold=True))] +
            [""] * n_dec
        )
        table_style_cmds.append(("SPAN", (0, row_idx), (-1, row_idx)))
        table_style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), COL_DISEASE_ROW))
        row_idx += 1

        for disease_name, disease_risk in diseases:
            row = [_label_para(disease_name, 1)] + [_risk_para(disease_risk.get(d, 0)) for d in active_decades]
            table_data.append(row)
            for col_i, d in enumerate(active_decades):
                r_val = disease_risk.get(d, 0)
                table_style_cmds.append(
                    ("BACKGROUND", (col_i + 1, row_idx), (col_i + 1, row_idx), RISK_CELL_COLOR[r_val])
                )
            row_idx += 1

        risk_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        risk_table.setStyle(TableStyle(table_style_cmds))
        story.append(KeepTogether([risk_table]))
        story.append(Spacer(1, 0.1*cm))

        # Legend
        legend_data = [[
            Paragraph("Chu giai:", _style("lgd0", size=7.5, bold=True)),
            _legend_cell("Thap",   COL_RISK1),
            _legend_cell("Trung binh (TB)", COL_RISK2),
            _legend_cell("Cao",    COL_RISK3),
            _legend_cell("Khong ap dung", COL_RISK0),
        ]]
        legend_table = Table(legend_data, colWidths=[1.5*cm, 1.8*cm, 3.0*cm, 1.3*cm, 3.0*cm])
        legend_table.setStyle(TableStyle([
            ("VALIGN",  (0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",  (0,0),(-1,-1), 2),
            ("RIGHTPADDING", (0,0),(-1,-1), 2),
            ("TOPPADDING",   (0,0),(-1,-1), 1),
            ("BOTTOMPADDING",(0,0),(-1,-1), 1),
        ]))
        story.append(legend_table)
        story.append(Spacer(1, 0.25*cm))

    # ── Footer ──
    story.append(HRFlowable(width="100%", thickness=0.8,
                             color=colors.HexColor("#aaaaaa"), spaceBefore=8))
    story.append(Paragraph(
        "Phong Nghien cuu Khi tuong nong nghiep va Dich vu khi hau  |  "
        "Vien Khoa hoc Khi tuong Thuy van Moi truong va Bien  |  "
        f"Ban tin phat hanh: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        _style("footer", size=7, align=TA_CENTER, color=colors.HexColor("#888888"))
    ))

    doc.build(story)
    return buf.getvalue()


def _section_header_para(text, bg_color, style):
    """Return a Table that looks like a colored section header."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    tbl = Table(
        [[text]],
        colWidths=["100%"],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), bg_color),
        ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
        ("FONT",          (0,0),(-1,-1), "DVSans-Bold", 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    return tbl


def _legend_cell(label, bg_color):
    """Return a small colored cell for the legend row."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    s = ParagraphStyle("lgd", fontName="DVSans", fontSize=7.5,
                        alignment=TA_CENTER, leading=10)
    tbl = Table([[Paragraph(label, s)]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), bg_color),
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#aaaaaa")),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
        ("RIGHTPADDING",  (0,0),(-1,-1), 3),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    return tbl


# ══════════════════════════════════════════════════════════════════════════════
# IDW + CACHE NOI SUY
# ══════════════════════════════════════════════════════════════════════════════

def _idw_knn(xi, yi, zi, query_xy, k=12, power=3.0, eps=1e-12):
    tree = cKDTree(np.column_stack([xi, yi]))
    dists, idxs = tree.query(query_xy, k=min(k, xi.size))
    if dists.ndim == 1:
        dists, idxs = dists[:, None], idxs[:, None]
    exact = dists <= eps
    out = np.empty(dists.shape[0], dtype=float)
    for r in np.where(exact.any(axis=1))[0]:
        out[r] = zi[idxs[r, np.where(exact[r])[0][0]]]
    rest = ~exact.any(axis=1)
    if np.any(rest):
        d, nn = dists[rest], idxs[rest]
        w = 1.0 / np.maximum(d, eps) ** power
        out[rest] = (w * zi[nn]).sum(axis=1) / w.sum(axis=1)
    return out


@st.cache_data(show_spinner=False)
def _compute_grid(lons_t, lats_t, vals_t, minx, miny, maxx, maxy, mask_wkt, GRID_N=400, SIGMA=1.0):
    xi, yi, zi = np.array(lons_t), np.array(lats_t), np.array(vals_t)
    gx_vec = np.linspace(minx, maxx, GRID_N)
    gy_vec = np.linspace(miny, maxy, GRID_N)
    gx, gy = np.meshgrid(gx_vec, gy_vec)
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
    gv = _idw_knn(xi, yi, zi, grid_xy).reshape(gx.shape)
    if SIGMA > 0:
        gv = gaussian_filter(gv, sigma=SIGMA)
    if mask_wkt:
        mask_shape = wkt_loads(mask_wkt)
        try:
            from shapely.vectorized import contains as shp_contains
            mask_flat = shp_contains(mask_shape, gx.ravel(), gy.ravel()).reshape(gx.shape)
        except (ImportError, AttributeError):
            prep_s = prep(mask_shape)
            mask_flat = np.array(
                [prep_s.contains(Point(float(px), float(py))) for px, py in grid_xy],
                dtype=bool).reshape(gx.shape)
        gv = np.where(mask_flat, gv, np.nan)
    return gx_vec, gy_vec, gv


@st.cache_data(show_spinner=False)
def _mpl_to_plotly(cmap_name, n=128):
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap(cmap_name)
    pos = np.linspace(0, 1, n)
    return [[p, f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"]
            for p, (r, g, b, _) in zip(pos, [cmap(v) for v in pos])]


# ══════════════════════════════════════════════════════════════════════════════
# BUILD MAP FIGURE
# ══════════════════════════════════════════════════════════════════════════════

def build_figure(lons, lats, vals, meta, title, boundary_data, show_xa):
    bounds = boundary_data.get("bounds")
    if bounds:
        minx, miny, maxx, maxy = bounds
    else:
        minx, miny, maxx, maxy = 106.3, 20.6, 108.3, 21.8

    BUF = 0.12
    plot_minx, plot_miny = minx - BUF, miny - BUF
    plot_maxx, plot_maxy = maxx + BUF, maxy + BUF

    buf_data = 1.5
    ok = ((lons >= minx - buf_data) & (lons <= maxx + buf_data) &
          (lats >= miny - buf_data) & (lats <= maxy + buf_data))
    xi, yi, zi = lons[ok], lats[ok], vals[ok]
    if xi.size == 0:
        return None, "Khong co diem du lieu trong vung Quang Ninh"

    mask_wkt = boundary_data.get("mask_wkt", "")
    gx_vec, gy_vec, gv_masked = _compute_grid(
        tuple(xi.tolist()), tuple(yi.tolist()), tuple(zi.tolist()),
        float(minx), float(miny), float(maxx), float(maxy), mask_wkt,
    )

    levels = sorted(meta.get("levels", list(range(-5, 6))))
    vmin, vmax = levels[0], levels[-1]
    gv_display = np.where(np.isnan(gv_masked), np.nan, np.clip(gv_masked, vmin, vmax))
    colorscale = _mpl_to_plotly(meta.get("cmap", "RdBu_r"))
    unit = meta.get("unit", "")

    fig = go.Figure()

    if "tinh_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["tinh_x"], y=boundary_data["tinh_y"],
            mode="lines", line=dict(color="#aab0b8", width=0.5),
            hoverinfo="skip", showlegend=False, name="",
        ))

    fig.add_trace(go.Contour(
        z=gv_display, x=gx_vec, y=gy_vec,
        colorscale=colorscale, zmin=vmin, zmax=vmax,
        autocontour=False,
        contours=dict(start=vmin, end=vmax,
                      size=float(np.min(np.diff(levels))) if len(levels)>1 else 1.0,
                      coloring="fill", showlines=False),
        colorbar=dict(
            title=dict(text=f"Chuan sai ({unit})", side="right", font=dict(size=12, family="Arial, sans-serif")),
            tickvals=levels, ticktext=[str(v) for v in levels],
            tickfont=dict(size=10), thickness=16, len=0.75,
            outlinewidth=1, outlinecolor="#aaa"),
        opacity=0.90, connectgaps=False,
        hovertemplate=f"Lon: %{{x:.3f}}E<br>Lat: %{{y:.3f}}N<br>Gia tri: %{{z:.2f}} {unit}<extra></extra>",
        name="Noi suy", showscale=True,
    ))

    if "qn_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["qn_x"], y=boundary_data["qn_y"],
            mode="lines", line=dict(color="#111111", width=2.2),
            hoverinfo="skip", showlegend=True, name="Ranh gioi Quang Ninh",
        ))

    xa_visible = True if show_xa else "legendonly"
    if "xa_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["xa_x"], y=boundary_data["xa_y"],
            mode="lines", line=dict(color="#e07b00", width=1.1, dash="dot"),
            hoverinfo="skip", visible=xa_visible,
            showlegend=True, name="Ranh gioi xa", legendgroup="xa_border",
        ))

    if "xa_lx" in boundary_data and boundary_data["xa_texts"]:
        fig.add_trace(go.Scatter(
            x=boundary_data["xa_lx"], y=boundary_data["xa_ly"],
            mode="text", text=boundary_data["xa_texts"],
            textfont=dict(size=9, color="#111111", family="Arial Unicode MS, Arial, sans-serif"),
            textposition="middle center", hoverinfo="skip",
            visible=xa_visible, showlegend=True, name="Ten xa", legendgroup="xa_label",
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, family="Arial, sans-serif"), x=0.5, xanchor="center"),
        xaxis=dict(title="Kinh do (E)", range=[plot_minx, plot_maxx],
                   fixedrange=True, tickformat=".2f",
                   scaleanchor="y", scaleratio=1, constrain="domain",
                   showgrid=True, gridcolor="rgba(180,180,180,0.3)", gridwidth=0.5),
        yaxis=dict(title="Vi do (N)", range=[plot_miny, plot_maxy],
                   fixedrange=True, tickformat=".2f",
                   showgrid=True, gridcolor="rgba(180,180,180,0.3)", gridwidth=0.5),
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#aaa", borderwidth=1, font=dict(size=10)),
        margin=dict(l=60, r=20, t=50, b=50), height=680,
        plot_bgcolor="white", paper_bgcolor="white",
        hovermode="closest", dragmode=False,
        modebar_remove=["zoom","pan","zoomIn2d","zoomOut2d","resetScale2d",
                         "lasso2d","select2d","autoScale2d",
                         "hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"],
    )
    return fig, None


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PANELS (Du bao khi hau mua)
# ══════════════════════════════════════════════════════════════════════════════

def render_var_panel(var_prefix, meta, period, month_idx, boundary_data, month_labels, state_key, show_xa):
    with st.spinner(f"Dang tai {meta['label']} ..."):
        nc_bytes = download_nc(period, var_prefix)
    if nc_bytes is None:
        st.session_state[state_key] = {"error": f"Khong tai duoc file NC: {var_prefix}.{period}.nc"}
        return
    with st.spinner("Dang doc du lieu ..."):
        lons, lats, vals, err = load_nc_data(nc_bytes, month_idx)
    if err:
        st.session_state[state_key] = {"error": f"Loi doc du lieu: {err}"}
        return
    month_str = month_labels[month_idx] if month_idx < len(month_labels) else f"Thang +{month_idx+1}"
    title = f"Chuan sai {meta['label']} - {month_str} (Ky {period[:4]}/{period[4:]})"
    with st.spinner("Dang noi suy va ve ban do ..."):
        fig, err2 = build_figure(lons, lats, vals, meta, title, boundary_data, show_xa)
    if err2:
        st.session_state[state_key] = {"error": err2}
        return
    st.session_state[state_key] = {
        "fig": fig,
        "filename": f"chuan_sai_{var_prefix.replace('.','_')}_{period}_t{month_idx+1}.png",
        "error": None,
    }


def display_panel(state_key):
    result = st.session_state.get(state_key)
    if result is None:
        return
    if result.get("error"):
        st.error(f"Loi: {result['error']}")
        return
    st.plotly_chart(
        result["fig"], use_container_width=True,
        config={
            "scrollZoom": False, "displayModeBar": True,
            "modeBarButtonsToRemove": ["zoom2d","pan2d","zoomIn2d","zoomOut2d",
                                        "autoScale2d","resetScale2d","lasso2d","select2d"],
            "toImageButtonOptions": {"format": "png", "filename": result["filename"], "scale": 2},
        },
    )
    st.caption("Hover vao ban do de xem gia tri. Bam legend de an/hien lop xa.")


@st.fragment
def _map_fragment(tab_key, var_dict, period, month_idx, boundary_data, month_labels, show_xa):
    state_key = f"map_{tab_key}"
    sel = st.selectbox(
        "Chon bien:", list(var_dict.keys()),
        format_func=lambda k: var_dict[k]["label"],
        key=f"sel_{tab_key}",
    )
    if st.button("Ve ban do", key=f"btn_{tab_key}", type="primary"):
        render_var_panel(sel, var_dict[sel], period, month_idx,
                         boundary_data, month_labels, state_key, show_xa)
    display_panel(state_key)


# ══════════════════════════════════════════════════════════════════════════════
# RENDER BAN TIN XA
# ══════════════════════════════════════════════════════════════════════════════

def render_commune_bulletin(commune_name, crops, period, month_labels,
                             df_r, df_t, df_decadal, xacsuat_data,
                             gdf_xa=None):
    yr, mo = int(period[:4]), int(period[4:])
    forecast_months = []
    for offset in range(1, 4):
        m2 = mo + offset
        m2 = ((m2 - 1) % 12) + 1
        forecast_months.append(m2)

    active_decades = []
    for offset in range(1, 4):
        m2 = mo + offset
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        for d in ["T1", "T2", "T3"]:
            active_decades.append(f"{d}/{m2}")

    decade_risks = compute_decade_risks(df_decadal)
    growth_stages_lua = {d: LUA_GROWTH_STAGES_VN.get(d, "") for d in active_decades}
    growth_stages_rau = {d: RAU_GROWTH_STAGES.get(d, "") for d in active_decades}

    start_m = month_labels[0].replace("Thang ", "")
    end_m   = month_labels[-1].replace("Thang ", "")

    st.markdown(
        f'<div class="commune-title">Ban tin canh bao khi hau thang {start_m} den {end_m} - Xa {commune_name}</div>',
        unsafe_allow_html=True
    )

    # ── Two-column layout: map + TBNN chart ──
    col_map, col_chart = st.columns([1, 2])

    with col_map:
        st.markdown("**Vi tri xa**")
        if gdf_xa is not None:
            commune_gdf = None
            for col in gdf_xa.columns:
                if col.upper() in ("TEN_XA", "TENXA", "XA", "NAME", "TEN"):
                    matches = gdf_xa[gdf_xa[col].str.contains(commune_name.split()[0], case=False, na=False)]
                    if not matches.empty:
                        commune_gdf = matches
                    break
            if commune_gdf is not None and not commune_gdf.empty:
                try:
                    centroid = commune_gdf.geometry.centroid.iloc[0]
                    xs, ys = [], []
                    for geom in commune_gdf.geometry:
                        if geom is None: continue
                        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
                        for poly in polys:
                            _x, _y = poly.exterior.xy
                            xs.extend(list(_x)); xs.append(None)
                            ys.extend(list(_y)); ys.append(None)
                    fig_map = go.Figure()
                    all_x, all_y = [], []
                    for geom in gdf_xa.geometry:
                        if geom is None: continue
                        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
                        for poly in polys:
                            _x, _y = poly.exterior.xy
                            all_x.extend(list(_x)); all_x.append(None)
                            all_y.extend(list(_y)); all_y.append(None)
                    fig_map.add_trace(go.Scatter(x=all_x, y=all_y, mode="lines",
                                                  line=dict(color="#cccccc", width=0.8),
                                                  hoverinfo="skip", showlegend=False))
                    fig_map.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                                  fill="toself", fillcolor="rgba(30,58,95,0.35)",
                                                  line=dict(color="#1e3a5f", width=2),
                                                  hoverinfo="skip", showlegend=False))
                    fig_map.add_trace(go.Scatter(x=[centroid.x], y=[centroid.y],
                                                  mode="text+markers",
                                                  text=[commune_name],
                                                  textposition="top center",
                                                  textfont=dict(size=11, color="#1e3a5f", family="Arial"),
                                                  marker=dict(size=8, color="#e53935"),
                                                  hoverinfo="skip", showlegend=False))
                    fig_map.update_layout(
                        height=220, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                                   scaleanchor="y", scaleratio=1),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor="white", paper_bgcolor="white", dragmode=False,
                    )
                    st.plotly_chart(fig_map, use_container_width=True,
                                    config={"displayModeBar": False})
                except Exception:
                    st.info(f"Xa **{commune_name}**")
            else:
                st.info(f"Xa **{commune_name}**")
        else:
            st.info(f"Xa **{commune_name}**")

    with col_chart:
        fig_clim = build_climate_normal_chart(commune_name, df_r, df_t, forecast_months)
        if fig_clim:
            st.plotly_chart(fig_clim, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Chua tai duoc du lieu TBNN cho xa nay.")

    # ── Probability table ──
    st.markdown("**Du bao khi hau xac suat**")
    if xacsuat_data and any(xacsuat_data.values()):
        html_table = render_xacsuat_table(xacsuat_data, month_labels)
        st.markdown(html_table, unsafe_allow_html=True)
    else:
        tbl_data = {"Bien": ["Nhiet do TB nhieu nam (%)", "Luong mua TB nhieu nam (mm)"]}
        for lbl in month_labels:
            m = lbl.replace("Thang ","").split("/")[0]
            tbl_data[f"Thang {m} - Thap hon (XSHC)"] = ["—", "—"]
            tbl_data[f"Thang {m} - Xap xi (XSCC)"]   = ["—", "—"]
            tbl_data[f"Thang {m} - Cao hon (XSVC)"]   = ["—", "—"]
        st.info("Du lieu xac suat chua co hoac chua tai duoc.")
        st.dataframe(pd.DataFrame(tbl_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Risk tables per crop ──
    for crop in crops:
        emoji = {"Lúa": "🌾", "Rau": "🥬", "Lợn": "🐷", "Gà": "🐔"}.get(crop, "🌿")
        crop_year = yr if mo + 3 <= 12 else yr + 1
        st.markdown(
            f'<div class="risk-header">{emoji} Muc do rui ro doi voi {crop} '
            f'giai doan {start_m} den {end_m} nam {crop_year}</div>',
            unsafe_allow_html=True
        )

        if crop == "Lúa":
            gs = growth_stages_lua
            diseases = [
                ("Ray", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
                ("Sau cuon la", {d: min(3, max(1, 2)) for d in active_decades}),
                ("Duc than", {d: 1 for d in active_decades}),
                ("Dao on", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
                ("Nam co bong", {d: 1 for d in active_decades}),
                ("Kho van", {d: 1 for d in active_decades}),
                ("Ray nau", {d: min(3, decade_risks.get("Lúa", {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Rau":
            gs = growth_stages_rau
            diseases = [
                ("Sau xanh", {d: 1 for d in active_decades}),
                ("Sau to", {d: 1 for d in active_decades}),
                ("Rep", {d: 1 for d in active_decades}),
                ("Bo nhay", {d: 1 for d in active_decades}),
                ("Benh thoi goc", {d: min(3, decade_risks.get("Rau", {}).get(d, 1)) for d in active_decades}),
                ("Suong mai", {d: min(3, decade_risks.get("Rau", {}).get(d, 1)) for d in active_decades}),
            ]
        elif crop == "Lợn":
            gs = None
            diseases = [
                ("Dich ta lon Chau Phi", {d: 1 for d in active_decades}),
                ("Dich ta lon co dien", {d: 1 for d in active_decades}),
                ("Viem phoi dinh suon", {d: 1 for d in active_decades}),
                ("Suyen lon", {d: 1 for d in active_decades}),
                ("Tai xanh (PRRS)", {d: 1 for d in active_decades}),
                ("Tieu chay do E.coli", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
                ("Dong dau lon", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
                ("Lo mom long mong", {d: 1 for d in active_decades}),
                ("Tu huyet trung lon", {d: min(3, decade_risks.get("Lợn", {}).get(d, 1)) for d in active_decades}),
            ]
        else:
            gs = None
            diseases = [
                ("Hen ga", {d: 1 for d in active_decades}),
                ("Cum gia cam DLC cao", {d: 1 for d in active_decades}),
                ("Cau trung ga", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
                ("Viem ruot hoai tu", {d: 1 for d in active_decades}),
                ("Newcastle", {d: 1 for d in active_decades}),
                ("Tu huyet trung gia cam", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
                ("Ky sinh trung duong mau", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
                ("Dau ga", {d: min(3, decade_risks.get("Gà", {}).get(d, 1)) for d in active_decades}),
            ]

        html_risk = render_risk_table(crop, active_decades, decade_risks, gs, diseases)
        st.markdown(html_risk, unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:11px; margin:-6px 0 10px 0;">'
            '<span style="background:#c8f7c5; padding:2px 8px; margin-right:6px; border-radius:3px;">Thap</span>'
            '<span style="background:#fff176; padding:2px 8px; margin-right:6px; border-radius:3px;">Trung binh (TB)</span>'
            '<span style="background:#ff8a65; padding:2px 8px; margin-right:6px; border-radius:3px;">Cao</span>'
            '<span style="background:#f0f0f0; padding:2px 8px; border-radius:3px;">Khong ap dung</span>'
            '</div>',
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# TRANG – TONG QUAN
# ══════════════════════════════════════════════════════════════════════════════

def page_tong_quan():
    st.title("Cong cu quan ly rui ro khi hau doi voi cay trong va vat nuoi tinh Quang Ninh")
    st.markdown(
        "He thong ho tro tao **ban tin canh bao khi hau** cho cac xa tai Quang Ninh, "
        "bao gom danh gia rui ro cho **Lua, Rau, Lon, Ga** theo tung ky thang."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("So xa", str(len(COMMUNE_CROPS)))
    c2.metric("Doi tuong nong nghiep", "4")
    c3.metric("Ky du bao", "3 thang")
    c4.metric("Ban tin da tao", "0")


# ══════════════════════════════════════════════════════════════════════════════
# TRANG – DU BAO KHI HAU MUA
# ══════════════════════════════════════════════════════════════════════════════

def page_du_bao():
    st.markdown('<div class="module-header">Du bao khi hau mua</div>', unsafe_allow_html=True)

    with st.spinner("Dang tai shapefile ..."):
        gdf_all_tinh, gdf_tinh_qn, gdf_xa = load_shapefiles()

    if gdf_all_tinh is None and gdf_xa is None:
        st.warning("Khong tai duoc shapefile - ban do se khong co ranh gioi.")

    boundary_data = build_boundary_traces_cached(gdf_all_tinh, gdf_tinh_qn, gdf_xa)

    with st.spinner("Kiem tra du lieu moi nhat ..."):
        periods = fetch_available_periods()
    if not periods:
        st.error("Khong ket noi duoc server hoac chua co du lieu.")
        return

    periods_desc = list(reversed(periods))
    yr_mo_labels = [f"{p[:4]}/{p[4:]}" for p in periods_desc]

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sel_idx = st.selectbox(
            "Ky du bao:", range(len(periods_desc)),
            format_func=lambda i: yr_mo_labels[i],
        )
        sel_period = periods_desc[sel_idx]

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = []
    for d in range(1, 4):
        m2 = mo + d
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        month_labels.append(f"Thang {m2:02d}/{y2}")

    with col2:
        month_idx = st.selectbox("Han du bao:", range(3),
                                  format_func=lambda i: month_labels[i])
    with col3:
        show_xa = st.toggle("Hien thi lop xa", value=False)

    st.markdown("---")
    tab_c, tab_e = st.tabs(["Chuan sai du bao khi hau", "Chuan sai du bao cuc doan"])

    with tab_c:
        _map_fragment("c", CLIMATE_VARS, sel_period, month_idx, boundary_data, month_labels, show_xa)
    with tab_e:
        _map_fragment("e", EXTREME_VARS, sel_period, month_idx, boundary_data, month_labels, show_xa)


# ══════════════════════════════════════════════════════════════════════════════
# TRANG – BAN TIN XA (với PDF Export)
# ══════════════════════════════════════════════════════════════════════════════

def page_ban_tin_xa():
    st.markdown('<div class="module-header">Ban tin canh bao rui ro khi hau</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3])

    with col1:
        with st.spinner("Kiem tra du lieu ..."):
            periods = fetch_available_periods()
        if not periods:
            st.error("Khong ket noi duoc server.")
            return

        periods_desc = list(reversed(periods))
        sel_idx = st.selectbox(
            "Ky du bao:",
            range(len(periods_desc)),
            format_func=lambda i: f"{periods_desc[i][:4]}/{periods_desc[i][4:]}",
        )
        sel_period = periods_desc[sel_idx]
        commune_list = list(COMMUNE_CROPS.keys())
        sel_commune = st.selectbox("Chon xa:", commune_list)

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = []
    for d in range(1, 4):
        m2 = mo + d
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        month_labels.append(f"Thang {m2:02d}/{y2}")

    with col2:
        st.markdown("**Ky du bao:**")
        st.info(f"Thang {month_labels[0].split('Thang ')[1]} → {month_labels[-1].split('Thang ')[1]}")
        st.markdown(f"**Doi tuong:** {', '.join(COMMUNE_CROPS.get(sel_commune, []))}")

    st.markdown("---")

    crops = COMMUNE_CROPS.get(sel_commune, [])

    with st.spinner("Dang tai du lieu ERA5 TBNN ..."):
        df_r, df_t = load_era5_data()

    with st.spinner("Dang tai du bao theo thap ..."):
        df_decadal = load_member_decadal(sel_period)

    with st.spinner("Dang tai du bao xac suat ..."):
        xacsuat_data = load_xacsuat_for_commune(sel_period, sel_commune)

    with st.spinner("Dang tai shapefile ..."):
        _, _, gdf_xa = load_shapefiles()

    # ══════════════════════════════════════════════════════════
    # PDF EXPORT BOX  ← PHẦN MỚI
    # ══════════════════════════════════════════════════════════
    with st.container():
        st.markdown('<div class="pdf-export-box">', unsafe_allow_html=True)
        exp_col1, exp_col2 = st.columns([3, 2])

        with exp_col1:
            st.markdown(
                "**Xuat ban tin PDF**  \n"
                f"Xa: **{sel_commune}**  |  "
                f"Thang {month_labels[0].split('Thang ')[1]} den "
                f"{month_labels[-1].split('Thang ')[1]}  |  "
                f"Doi tuong: {', '.join(crops)}"
            )

        with exp_col2:
            if st.button("Tao PDF ban tin", type="primary", use_container_width=True,
                          icon="📄"):
                with st.spinner("Dang tao file PDF..."):
                    try:
                        pdf_bytes = generate_bulletin_pdf(
                            commune_name=sel_commune,
                            crops=crops,
                            period=sel_period,
                            month_labels=month_labels,
                            df_r=df_r,
                            df_t=df_t,
                            df_decadal=df_decadal,
                            xacsuat_data=xacsuat_data,
                        )
                        fname = (
                            f"BanTin_{sel_commune.replace(' ','_')}_"
                            f"{sel_period}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        )
                        st.session_state["pdf_bytes"] = pdf_bytes
                        st.session_state["pdf_fname"] = fname
                        st.success(f"Tao PDF thanh cong! Nhan nut tai xuong ben duoi.")
                    except Exception as e:
                        st.error(f"Loi tao PDF: {e}")

            # Show download button if PDF is ready for this commune/period
            if "pdf_bytes" in st.session_state and "pdf_fname" in st.session_state:
                st.download_button(
                    label="Tai xuong PDF",
                    data=st.session_state["pdf_bytes"],
                    file_name=st.session_state["pdf_fname"],
                    mime="application/pdf",
                    use_container_width=True,
                    icon="⬇️",
                )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Render bulletin on screen ──
    render_commune_bulletin(
        commune_name=sel_commune,
        crops=crops,
        period=sel_period,
        month_labels=month_labels,
        df_r=df_r,
        df_t=df_t,
        df_decadal=df_decadal,
        xacsuat_data=xacsuat_data,
        gdf_xa=gdf_xa,
    )


def page_ban_tin_da_luu():
    st.markdown('<div class="module-header">Ban tin da luu</div>', unsafe_allow_html=True)
    st.info("Module dang phat trien.")


def page_export():
    st.markdown('<div class="module-header">Export ban tin</div>', unsafe_allow_html=True)
    st.info("Module dang phat trien.")


def page_phan_hoi():
    st.markdown('<div class="module-header">Phan hoi</div>', unsafe_allow_html=True)
    st.info("Module dang phat trien.")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR & DIEU HUONG
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## Ban tin Khi hau")
    st.markdown("**Quang Ninh - Nong nghiep**")
    st.markdown("---")
    menu = st.radio("Chon module:", [
        "Tong quan",
        "Du bao khi hau mua",
        "Ban tin canh bao rui ro khi hau",
        "Ban tin da luu",
        "Export ban tin",
        "Phan hoi",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("Phong Nghien cuu Khi tuong nong nghiep va Dich vu khi hau")
    st.markdown("Vien Khoa hoc Khi tuong Thuy van Moi truong va Bien")
    st.markdown("---")
    st.markdown("*Phien ban 1.4.0 - 06/2026*")

if   menu == "Tong quan":                               page_tong_quan()
elif menu == "Du bao khi hau mua":                      page_du_bao()
elif menu == "Ban tin canh bao rui ro khi hau":         page_ban_tin_xa()
elif menu == "Ban tin da luu":                          page_ban_tin_da_luu()
elif menu == "Export ban tin":                          page_export()
elif menu == "Phan hoi":                                page_phan_hoi()
