# -*- coding: utf-8 -*-
"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
THAY ĐỔI v1.4.0:
  [FIX]  Bảng xác suất: dùng đúng file XSHC/XSCC/XSVC.T2m.nc và XSHC/XSCC/XSVC.R.nc
  [FIX]  Biểu đồ TBNN: Việt hóa toàn bộ, giai đoạn 1981–2024
  [PERF] Giữ nguyên toàn bộ code v1.3.0
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
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL    = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
XACSUAT_URL = "http://222.254.32.10/forecast/Detai_QuangNinh/xacsuat/domain_d02/"
MEMBER_URL  = "http://222.254.32.10/forecast/Detai_QuangNinh/trungbinhmember/domain_d02/"
SHP_QN_URL  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"
ERA5_R_URL  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/R_ERA5_CDFT_corrected.xlsx"
ERA5_T_URL  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/T2m_ERA5_QM_corrected.xlsx"
ECOLOGY_URL = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/B%E1%BA%A3ng%20sinh%20th%C3%A1i%20v%C3%A0%20m%C3%B9a%20v%E1%BB%A5_19-6.xlsx"

# ── Giai đoạn TBNN ──────────────────────────────────────────────────────────
CLIM_YEAR_START = 1981
CLIM_YEAR_END   = 2024

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
    "Bình Khê":   "binhkhe",
    "Mạo Khê":    "maokhe",
    "Hoàng Quế":  "hoangque",
}

LUA_GROWTH_STAGES = {
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
    "Gieo, nảy mầm": (10, 45),
    "Mạ":             (12, 35),
    "Đẻ nhánh":       (9,  33),
    "Làm đòng":       (15, 38),
    "Phân hóa hoa":   (15, 38),
    "Trỗ – thụ phấn": (22, 38),
}

PIG_THI_RISK     = {"normal": 74, "warn": 78, "danger": 83, "critical": 84}
CHICKEN_THI_RISK = {"normal": 70, "warn": 75, "danger": 81, "critical": 81}

RISK_LABELS  = {0: "—", 1: "Thấp", 2: "Trung bình", 3: "Cao"}
RISK_COLORS  = {0: "#f0f0f0", 1: "#c8f7c5", 2: "#fff176", 3: "#ff8a65"}
DECADAL_LABELS = ["T1/6","T2/6","T3/6","T1/7","T2/7","T3/7","T1/8","T2/8","T3/8"]

# Nhãn tháng tiếng Việt viết tắt cho biểu đồ TBNN
MONTHS_VN = ["Th.1","Th.2","Th.3","Th.4","Th.5","Th.6",
             "Th.7","Th.8","Th.9","Th.10","Th.11","Th.12"]


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
# ERA5 CLIMATE DATA  (giai đoạn CLIM_YEAR_START – CLIM_YEAR_END)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def load_era5_data():
    """Load ERA5 bias-corrected temperature and rainfall for all communes."""
    try:
        r_r = requests.get(ERA5_R_URL, timeout=30)
        r_t = requests.get(ERA5_T_URL, timeout=30)
        if r_r.status_code != 200 or r_t.status_code != 200:
            return None, None

        df_r = pd.read_excel(io.BytesIO(r_r.content), sheet_name=0, header=None)
        df_t = pd.read_excel(io.BytesIO(r_t.content), sheet_name=0, header=None)

        # Row 0 = col names, rows 1-2 = lon/lat metadata, rows 3+ = data
        cols_r = df_r.iloc[0].tolist()
        df_r.columns = cols_r
        df_r = df_r.iloc[3:].copy()
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
    """
    Tính TBNN giai đoạn CLIM_YEAR_START–CLIM_YEAR_END cho một xã.
    Trả về dict: {month: {"T": mean_T, "R": total_R}} với month 1-12.
    """
    col_key = COMMUNE_COL_MAP.get(commune_name)
    if col_key is None or df_r is None or df_t is None:
        return {}

    # Lọc theo giai đoạn chuẩn
    mask_r = (df_r["year"] >= CLIM_YEAR_START) & (df_r["year"] <= CLIM_YEAR_END)
    mask_t = (df_t["year"] >= CLIM_YEAR_START) & (df_t["year"] <= CLIM_YEAR_END)

    r_col = next((c for c in df_r.columns if str(c).lower().strip() == col_key.lower()), None)
    t_col = next((c for c in df_t.columns if str(c).lower().strip() == col_key.lower()), None)

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
        result[m] = {
            "T": round(float(temp_monthly), 1) if pd.notna(temp_monthly) else 0,
            "R": round(float(rain_monthly),  1) if pd.notna(rain_monthly)  else 0,
        }
    return result


# ══════════════════════════════════════════════════════════════════════════════
# NETCDF DATA (Dự báo khí hậu mùa)
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
    if base_url is None:
        base_url = BASE_URL
    url = f"{base_url}{period}/{var_prefix}.{period}.nc"
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.status_code == 200 else None
    except Exception:
        return None


# ── [v1.4] Tải file xác suất theo tên XSHC/XSCC/XSVC ────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def download_xacsuat_nc(period: str, prefix: str, varname: str):
    """
    Tải file xác suất với tên dạng: XSHC.T2m.<period>.nc
    prefix = "XSHC" | "XSCC" | "XSVC"
    varname = "T2m" | "R"
    URL mẫu: XACSUAT_URL/<period>/XSHC.T2m.<period>.nc
    """
    url = f"{XACSUAT_URL}{period}/{prefix}.{varname}.{period}.nc"
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
            return None, None, None, "Không tìm thấy biến dữ liệu"
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'month' in d.lower()]
        if time_dims:
            da = da.isel({time_dims[0]: min(month_idx, da.sizes[time_dims[0]] - 1)})
        lat_names = [d for d in da.dims if 'lat' in d.lower() or d == 'y']
        lon_names = [d for d in da.dims if 'lon' in d.lower() or d == 'x']
        if not lat_names or not lon_names:
            return None, None, None, "Không tìm thấy chiều lat/lon"
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
# LOAD PROBABILITY DATA  [v1.4 – dùng XSHC/XSCC/XSVC riêng biệt]
# ══════════════════════════════════════════════════════════════════════════════

def _extract_spatial_mean_from_nc(nc_bytes, month_idx):
    """
    Đọc file NC, lấy time-slice month_idx rồi tính trung bình không gian.
    Trả về float hoặc None.
    """
    if nc_bytes is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes); tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        coord_names = {c.lower() for c in ds.coords}
        data_vars = [v for v in ds.data_vars if v.lower() not in coord_names]
        if not data_vars:
            ds.close(); os.unlink(tmp); return None
        da = ds[data_vars[0]]
        time_dims = [d for d in da.dims if 'time' in d.lower() or 'month' in d.lower()]
        if time_dims:
            n = da.sizes[time_dims[0]]
            da = da.isel({time_dims[0]: min(month_idx, n - 1)})
        val = float(da.mean().values)
        ds.close(); os.unlink(tmp)
        return round(val, 1) if np.isfinite(val) else None
    except Exception:
        try: os.unlink(tmp)
        except: pass
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_xacsuat_for_commune(period: str, commune_name: str, month_offsets=(1, 2, 3)):
    """
    Tải 6 file xác suất (XSHC/XSCC/XSVC × T2m/R) và trả về:
      {month_label: {"T": (thap%, xapxi%, caohon%), "R": (thap%, xapxi%, caohon%)}}

    File tải:  XACSUAT_URL/<period>/XSHC.T2m.<period>.nc  (và XSCC, XSVC, .R)
    month_idx tương ứng offset-1 (0=tháng+1, 1=tháng+2, 2=tháng+3).
    """
    yr, mo = int(period[:4]), int(period[4:])

    # Tải 6 file một lần (cache theo period)
    nc_cache = {}
    for pfx in ("XSHC", "XSCC", "XSVC"):
        for var in ("T2m", "R"):
            key = f"{pfx}.{var}"
            nc_cache[key] = download_xacsuat_nc(period, pfx, var)

    result = {}
    for offset in month_offsets:
        m2 = mo + offset
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        label = f"Tháng {m2:02d}/{y2}"
        midx  = offset - 1   # time index trong file NC

        def _prob(var):
            vals = []
            for pfx in ("XSHC", "XSCC", "XSVC"):
                v = _extract_spatial_mean_from_nc(nc_cache.get(f"{pfx}.{var}"), midx)
                vals.append(v)
            if any(x is not None for x in vals):
                # Nếu giá trị đã là % thì không chuẩn hoá, nếu là xác suất 0-1 thì *100
                cleaned = [v if v is not None else 0.0 for v in vals]
                total = sum(cleaned)
                if total <= 0:
                    return (None, None, None)
                # Nếu tổng ≈ 1 → đang ở dạng 0-1, chuyển sang %
                if total <= 1.5:
                    cleaned = [v * 100 for v in cleaned]
                    total = sum(cleaned)
                return tuple(round(v / total * 100) for v in cleaned)
            return (None, None, None)

        result[label] = {
            "T": _prob("T2m"),
            "R": _prob("R"),
        }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# LOAD MEMBER DATA (trung bình member - daily T2m, RH, R)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_member_decadal(period: str, month_offsets=(1, 2, 3)):
    yr, mo = int(period[:4]), int(period[4:])
    rows = []

    for offset in month_offsets:
        m2 = mo + offset
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1

        t_bytes  = download_nc(period, "T2m",  MEMBER_URL)
        rh_bytes = download_nc(period, "RH2m", MEMBER_URL)
        r_bytes  = download_nc(period, "R",    MEMBER_URL)

        for decade_idx, decade_label in enumerate(["T1", "T2", "T3"]):
            label = f"{decade_label}/{m2}"
            t_val  = _extract_decadal_mean(t_bytes,  offset - 1, decade_idx, is_sum=False)
            rh_val = _extract_decadal_mean(rh_bytes, offset - 1, decade_idx, is_sum=False)
            r_val  = _extract_decadal_mean(r_bytes,  offset - 1, decade_idx, is_sum=True)
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
            start  = decade_idx * 10
            end    = min(start + 10, n_days)
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
    if T is None or RH is None:
        return None
    return round((1.8*T + 32) - ((0.55 - 0.0055*RH) * (1.8*T - 26)), 1)

def thi_to_risk_pig(thi):
    if thi is None: return 0
    if thi < 75:    return 1
    if thi <= 78:   return 2
    return 3

def temp_to_risk_lua(T, stage):
    if T is None or stage not in LUA_TEMP_RISK: return 0
    cold, hot = LUA_TEMP_RISK[stage]
    if T < cold or T >= hot:             return 3
    if T < cold + 2 or T >= hot - 3:    return 2
    return 1

def rain_to_risk(R_sum, threshold_drought=20, threshold_flood=150):
    if R_sum is None: return 0
    if R_sum < threshold_drought or R_sum > threshold_flood: return 3
    if R_sum < threshold_drought + 20 or R_sum > threshold_flood - 50: return 2
    return 1

def compute_decade_risks(df_decadal):
    if df_decadal is None or df_decadal.empty:
        return {}
    risks = {crop: {} for crop in ["Lúa","Rau","Lợn","Gà"]}
    for _, row in df_decadal.iterrows():
        decade = row["decade"]
        T  = row.get("T2m")
        RH = row.get("RH2m", 75)
        R  = row.get("R")

        stage = LUA_GROWTH_STAGES.get(decade, "")
        risks["Lúa"][decade] = max(temp_to_risk_lua(T, stage) if stage else 0, rain_to_risk(R))

        t_rau = 0
        if T is not None:
            t_rau = 3 if (T > 38 or T < 10) else (2 if (T > 35 or T < 15) else 1)
        risks["Rau"][decade] = max(t_rau, rain_to_risk(R))

        risks["Lợn"][decade] = thi_to_risk_pig(compute_pig_thi(T, RH or 75))

        t_ga = 0
        if T is not None:
            t_ga = 3 if T > 35 else (2 if (T > 30 or T < 15) else 1)
        risks["Gà"][decade] = max(t_ga, rain_to_risk(R, 10, 100))

    return risks


# ══════════════════════════════════════════════════════════════════════════════
# BIỂU ĐỒ TBNN  [v1.4 – Việt hóa + giai đoạn 1981-2024]
# ══════════════════════════════════════════════════════════════════════════════

def build_climate_normal_chart(commune_name, df_r, df_t, forecast_months):
    """
    Biểu đồ kết hợp cột (lượng mưa) + đường (nhiệt độ) theo 12 tháng.
    - Nhãn trục X tiếng Việt: Th.1 … Th.12
    - Giai đoạn TBNN: CLIM_YEAR_START–CLIM_YEAR_END
    - Tháng dự báo được tô màu đỏ (cột) + khung nền vàng nhạt
    """
    clim = get_commune_monthly_climate(commune_name, df_r, df_t)
    if not clim:
        return None

    R_vals = [clim.get(m, {}).get("R", 0) for m in range(1, 13)]
    T_vals = [clim.get(m, {}).get("T", 0) for m in range(1, 13)]

    bar_colors = ["#e53935" if m in forecast_months else "#1565c0"
                  for m in range(1, 13)]

    fig = go.Figure()

    # Cột lượng mưa
    fig.add_trace(go.Bar(
        x=MONTHS_VN, y=R_vals,
        name="Lượng mưa (mm)",
        marker_color=bar_colors,
        yaxis="y1",
        hovertemplate="<b>%{x}</b><br>Mưa: %{y:.0f} mm<extra></extra>",
    ))

    # Đường nhiệt độ
    fig.add_trace(go.Scatter(
        x=MONTHS_VN, y=T_vals,
        name="Nhiệt độ (°C)",
        mode="lines+markers",
        line=dict(color="#e65100", width=2.5),
        marker=dict(color="#e65100", size=7, symbol="circle"),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Nhiệt độ: %{y:.1f}°C<extra></extra>",
    ))

    # Nền vàng nhạt cho tháng dự báo
    for m in forecast_months:
        fig.add_vrect(
            x0=m - 1.5, x1=m - 0.5,          # index trong MONTHS_VN (0-based)
            fillcolor="rgba(255,235,59,0.18)",
            line_width=0,
            annotation_text=f"T.{m}",
            annotation_position="top",
            annotation_font=dict(size=9, color="#b71c1c"),
        )

    fig.update_layout(
        title=dict(
            text=(f"<b>Diễn biến khí hậu giai đoạn {CLIM_YEAR_START}–{CLIM_YEAR_END}"
                  f"<br><sup>Xã {commune_name} – Tháng dự báo tô đỏ</sup></b>"),
            font=dict(size=12, family="Arial"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            tickfont=dict(size=11),
            showgrid=False,
            fixedrange=True,
        ),
        yaxis=dict(
            title=dict(text="Lượng mưa (mm)", font=dict(color="#1565c0", size=11)),
            tickfont=dict(color="#1565c0", size=10),
            range=[0, max(R_vals) * 1.3 if max(R_vals) > 0 else 400],
            showgrid=True,
            gridcolor="rgba(180,180,180,0.3)",
            fixedrange=True,
        ),
        yaxis2=dict(
            title=dict(text="Nhiệt độ (°C)", font=dict(color="#e65100", size=11)),
            tickfont=dict(color="#e65100", size=10),
            overlaying="y", side="right",
            range=[min(T_vals) - 3, max(T_vals) + 5] if T_vals else [15, 40],
            showgrid=False,
            fixedrange=True,
        ),
        legend=dict(
            x=0.01, y=-0.22, orientation="h",
            bgcolor="rgba(255,255,255,0.85)",
            font=dict(size=11),
        ),
        height=295,
        margin=dict(l=55, r=65, t=60, b=55),
        plot_bgcolor="white",
        paper_bgcolor="white",
        bargap=0.18,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# BẢNG XÁC SUẤT  [v1.4]
# ══════════════════════════════════════════════════════════════════════════════

def render_xacsuat_table(xacsuat_data, month_labels):
    """
    Bảng xác suất giống ảnh mẫu.
    xacsuat_data: {month_label: {"T": (thap, xapxi, caohon), "R": (thap, xapxi, caohon)}}
    """
    def _fmt(v):
        return str(int(round(v))) if v is not None else "—"

    rows_T = []
    rows_R = []
    for lbl in month_labels:
        probs = xacsuat_data.get(lbl, {})
        t_vals = probs.get("T", (None, None, None))
        r_vals = probs.get("R", (None, None, None))
        rows_T.extend([_fmt(v) for v in t_vals])
        rows_R.extend([_fmt(v) for v in r_vals])

    html = """
    <table style="border-collapse:collapse; width:100%; font-size:13px; font-family:Arial;">
      <thead>
        <tr style="background:#1e3a5f; color:white; text-align:center;">
          <th rowspan="2" style="border:1px solid #aaa; padding:5px 10px; width:200px;">Tháng</th>
    """
    for lbl in month_labels:
        m = lbl.replace("Tháng ","").split("/")[0]
        html += f'<th colspan="3" style="border:1px solid #aaa; padding:5px 8px;">{m}</th>'
    html += "</tr><tr style='background:#2d6a4f; color:white; text-align:center;'>"
    for _ in month_labels:
        for label, code in [("Thấp hơn","XSHC"),("Xấp xỉ","XSCC"),("Cao hơn","XSVC")]:
            html += (f'<th style="border:1px solid #aaa; padding:4px 6px;">'
                     f'{label}<br><small>({code})</small></th>')
    html += "</tr></thead><tbody>"

    for row_data, var_label in [
        (rows_T, "Nhiệt độ TB nhiều năm (%)"),
        (rows_R, "Lượng mưa TB nhiều năm (mm)"),
    ]:
        html += (f'<tr><td style="border:1px solid #aaa; padding:5px 10px;'
                 f' background:#e8f4f8; font-weight:bold;">{var_label}</td>')
        for val in row_data:
            html += f'<td style="border:1px solid #aaa; padding:5px 8px; text-align:center;">{val}</td>'
        html += "</tr>"

    html += "</tbody></table>"
    return html


# ══════════════════════════════════════════════════════════════════════════════
# BẢNG RỦI RO
# ══════════════════════════════════════════════════════════════════════════════

def render_risk_table(crop_name, decades, decade_risks, growth_stages=None, diseases=None):
    risk_for_crop = decade_risks.get(crop_name, {})
    RISK_COLOR = {0:"#f0f0f0", 1:"#c8f7c5", 2:"#fff176", 3:"#ff8a65"}
    RISK_TEXT  = {0:"—",       1:"Thấp",    2:"TB",      3:"Cao"}

    def _risk_cell(r):
        c = RISK_COLOR.get(r, "#f0f0f0")
        t = RISK_TEXT.get(r, "—")
        return (f'<td style="border:1px solid #ccc; padding:3px 6px; text-align:center;'
                f' background:{c}; font-weight:bold; font-size:12px;">{t}</td>')

    col_w = 70
    head_style  = f"border:1px solid #ccc; padding:4px 6px; text-align:center; background:#1e3a5f; color:white; font-size:12px;"
    row_style   = "border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#f8f9fa;"
    group_style = "border:1px solid #ccc; padding:3px 8px; font-size:12px; background:#e3f2fd; font-weight:bold;"

    html = '<table style="border-collapse:collapse; width:100%; margin-bottom:12px;">'
    html += '<thead><tr>'
    html += f'<th style="{head_style} width:180px;">Giai đoạn</th>'
    for d in decades:
        html += f'<th style="{head_style} width:{col_w}px;">{d}</th>'
    html += '</tr>'

    if growth_stages:
        html += '<tr>'
        html += f'<td style="{group_style}">Chu kỳ sinh trưởng</td>'
        for d in decades:
            stage = growth_stages.get(d, "")
            html += (f'<td style="border:1px solid #ccc; padding:3px 4px;'
                     f' text-align:center; font-size:11px; background:#fff9e6;">{stage}</td>')
        html += '</tr>'
    html += '</thead><tbody>'

    html += (f'<tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px;'
             f' background:#c5e1a5; font-weight:bold; font-size:12px;">Rủi ro khí hậu</td></tr>')

    if crop_name in ("Lợn","Gà"):
        climate_rows = [
            ("Rủi ro nắng nóng / giá lạnh", risk_for_crop),
            ("Rủi ro mưa lớn",              risk_for_crop),
        ]
    else:
        climate_rows = [
            ("Rủi ro hạn hán",              risk_for_crop),
            ("Rủi ro nắng nóng / giá lạnh", risk_for_crop),
            ("Rủi ro mưa lớn",              risk_for_crop),
        ]

    for row_label, row_risk in climate_rows:
        html += '<tr>'
        html += f'<td style="{row_style} padding-left:16px;">{row_label}</td>'
        for d in decades:
            html += _risk_cell(row_risk.get(d, 0))
        html += '</tr>'

    if diseases:
        html += (f'<tr><td colspan="{len(decades)+1}" style="border:1px solid #ccc; padding:3px 8px;'
                 f' background:#ffe082; font-weight:bold; font-size:12px;">'
                 f'Rủi ro sinh vật hại / dịch bệnh</td></tr>')
        for disease_name, disease_risk in diseases:
            html += '<tr>'
            html += f'<td style="{row_style} padding-left:16px;">{disease_name}</td>'
            for d in decades:
                html += _risk_cell(disease_risk.get(d, 0))
            html += '</tr>'

    html += '</tbody></table>'
    return html


# ══════════════════════════════════════════════════════════════════════════════
# IDW + CACHE NỘI SUY
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
def _compute_grid(lons_t, lats_t, vals_t, minx, miny, maxx, maxy, mask_wkt,
                  GRID_N=400, SIGMA=1.0):
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
# BUILD MAP FIGURE (Dự báo khí hậu mùa)
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
        return None, "Không có điểm dữ liệu trong vùng Quảng Ninh"

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
                      size=float(np.min(np.diff(levels))) if len(levels) > 1 else 1.0,
                      coloring="fill", showlines=False),
        colorbar=dict(
            title=dict(text=f"Chuẩn sai ({unit})", side="right",
                       font=dict(size=12, family="Arial, sans-serif")),
            tickvals=levels, ticktext=[str(v) for v in levels],
            tickfont=dict(size=10), thickness=16, len=0.75,
            outlinewidth=1, outlinecolor="#aaa"),
        opacity=0.90, connectgaps=False,
        hovertemplate=f"Lon: %{{x:.3f}}°E<br>Lat: %{{y:.3f}}°N<br>Giá trị: %{{z:.2f}} {unit}<extra></extra>",
        name="Nội suy", showscale=True,
    ))

    if "qn_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["qn_x"], y=boundary_data["qn_y"],
            mode="lines", line=dict(color="#111111", width=2.2),
            hoverinfo="skip", showlegend=True, name="Ranh giới Quảng Ninh",
        ))

    xa_visible = True if show_xa else "legendonly"
    if "xa_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["xa_x"], y=boundary_data["xa_y"],
            mode="lines", line=dict(color="#e07b00", width=1.1, dash="dot"),
            hoverinfo="skip", visible=xa_visible,
            showlegend=True, name="Ranh giới xã", legendgroup="xa_border",
        ))

    if "xa_lx" in boundary_data and boundary_data["xa_texts"]:
        fig.add_trace(go.Scatter(
            x=boundary_data["xa_lx"], y=boundary_data["xa_ly"],
            mode="text", text=boundary_data["xa_texts"],
            textfont=dict(size=9, color="#111111", family="Arial Unicode MS, Arial, sans-serif"),
            textposition="middle center", hoverinfo="skip",
            visible=xa_visible, showlegend=True, name="Tên xã", legendgroup="xa_label",
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, family="Arial, sans-serif"),
                   x=0.5, xanchor="center"),
        xaxis=dict(title="Kinh độ (°E)", range=[plot_minx, plot_maxx],
                   fixedrange=True, tickformat=".2f",
                   scaleanchor="y", scaleratio=1, constrain="domain",
                   showgrid=True, gridcolor="rgba(180,180,180,0.3)", gridwidth=0.5),
        yaxis=dict(title="Vĩ độ (°N)", range=[plot_miny, plot_maxy],
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
# RENDER PANELS (Dự báo khí hậu mùa)
# ══════════════════════════════════════════════════════════════════════════════

def render_var_panel(var_prefix, meta, period, month_idx, boundary_data,
                     month_labels, state_key, show_xa):
    with st.spinner(f"⏳ Đang tải {meta['label']} …"):
        nc_bytes = download_nc(period, var_prefix)
    if nc_bytes is None:
        st.session_state[state_key] = {"error": f"Không tải được file NC: {var_prefix}.{period}.nc"}
        return
    with st.spinner("🔄 Đang đọc dữ liệu …"):
        lons, lats, vals, err = load_nc_data(nc_bytes, month_idx)
    if err:
        st.session_state[state_key] = {"error": f"Lỗi đọc dữ liệu: {err}"}
        return
    month_str = month_labels[month_idx] if month_idx < len(month_labels) else f"Tháng +{month_idx+1}"
    title = f"Chuẩn sai {meta['label']} – {month_str} (Kỳ {period[:4]}/{period[4:]})"
    with st.spinner("🗺️ Đang nội suy và vẽ bản đồ …"):
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
    if result is None: return
    if result.get("error"):
        st.error(f"❌ {result['error']}"); return
    st.plotly_chart(result["fig"], use_container_width=True, config={
        "scrollZoom": False, "displayModeBar": True,
        "modeBarButtonsToRemove": ["zoom2d","pan2d","zoomIn2d","zoomOut2d",
                                   "autoScale2d","resetScale2d","lasso2d","select2d"],
        "toImageButtonOptions": {"format":"png","filename":result["filename"],"scale":2},
    })
    st.caption("💡 Hover vào bản đồ để xem giá trị. Bấm legend để ẩn/hiện lớp xã.")


@st.fragment
def _map_fragment(tab_key, var_dict, period, month_idx, boundary_data, month_labels, show_xa):
    state_key = f"map_{tab_key}"
    sel = st.selectbox("Chọn biến:", list(var_dict.keys()),
                       format_func=lambda k: var_dict[k]["label"],
                       key=f"sel_{tab_key}")
    if st.button("🗺️ Vẽ bản đồ", key=f"btn_{tab_key}", type="primary"):
        render_var_panel(sel, var_dict[sel], period, month_idx,
                         boundary_data, month_labels, state_key, show_xa)
    display_panel(state_key)


# ══════════════════════════════════════════════════════════════════════════════
# RENDER BẢN TIN XÃ
# ══════════════════════════════════════════════════════════════════════════════

def render_commune_bulletin(commune_name, crops, period, month_labels,
                             df_r, df_t, df_decadal, xacsuat_data, gdf_xa=None):
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
        for d in ["T1","T2","T3"]:
            active_decades.append(f"{d}/{m2}")

    decade_risks      = compute_decade_risks(df_decadal)
    growth_stages_lua = {d: LUA_GROWTH_STAGES.get(d, "") for d in active_decades}
    growth_stages_rau = {d: RAU_GROWTH_STAGES.get(d, "") for d in active_decades}

    start_m = month_labels[0].replace("Tháng ", "")
    end_m   = month_labels[-1].replace("Tháng ", "")

    st.markdown(
        f'<div class="commune-title">📋 Bản tin cảnh báo khí hậu tháng {start_m} đến {end_m}'
        f' – Xã {commune_name}</div>',
        unsafe_allow_html=True,
    )

    # ── Bản đồ + Biểu đồ TBNN ──
    col_map, col_chart = st.columns([1, 2])

    with col_map:
        st.markdown("**📍 Vị trí xã**")
        if gdf_xa is not None:
            commune_gdf = None
            for col in gdf_xa.columns:
                if col.upper() in ("TEN_XA","TENXA","XA","NAME","TEN"):
                    matches = gdf_xa[gdf_xa[col].str.contains(
                        commune_name.split()[0], case=False, na=False)]
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
                        mode="text+markers", text=[commune_name],
                        textposition="top center",
                        textfont=dict(size=11, color="#1e3a5f", family="Arial"),
                        marker=dict(size=8, color="#e53935"),
                        hoverinfo="skip", showlegend=False))
                    fig_map.update_layout(
                        height=240, margin=dict(l=10,r=10,t=10,b=10),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                                   scaleanchor="y", scaleratio=1),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor="white", paper_bgcolor="white", dragmode=False,
                    )
                    st.plotly_chart(fig_map, use_container_width=True,
                                    config={"displayModeBar": False})
                except Exception:
                    st.info(f"Xã **{commune_name}**")
            else:
                st.info(f"Xã **{commune_name}**")
        else:
            st.info(f"Xã **{commune_name}**")

    with col_chart:
        fig_clim = build_climate_normal_chart(commune_name, df_r, df_t, forecast_months)
        if fig_clim:
            st.plotly_chart(fig_clim, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info(f"⚠️ Chưa tải được dữ liệu TBNN ({CLIM_YEAR_START}–{CLIM_YEAR_END}) cho xã này.")

    # ── Bảng xác suất ──
    st.markdown("**📊 Dự báo khí hậu xác suất**")
    has_data = xacsuat_data and any(
        any(v is not None for v in probs.get("T",(None,None,None)) + probs.get("R",(None,None,None)))
        for probs in xacsuat_data.values()
    )
    if has_data:
        html_table = render_xacsuat_table(xacsuat_data, month_labels)
        st.markdown(html_table, unsafe_allow_html=True)
    else:
        # Fallback placeholder
        tbl_data = {"Biến": ["Nhiệt độ TB nhiều năm (%)","Lượng mưa TB nhiều năm (mm)"]}
        for lbl in month_labels:
            m = lbl.replace("Tháng ","").split("/")[0]
            for code in ["XSHC","XSCC","XSVC"]:
                tbl_data[f"Tháng {m} – {code}"] = ["—","—"]
        st.info("ℹ️ Dữ liệu xác suất chưa tải được.")
        st.dataframe(pd.DataFrame(tbl_data), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Bảng rủi ro theo cây/con ──
    for crop in crops:
        emoji = {"Lúa":"🌾","Rau":"🥬","Lợn":"🐷","Gà":"🐔"}.get(crop,"🌿")
        st.markdown(
            f'<div class="risk-header">{emoji} Mức độ rủi ro đối với {crop} '
            f'giai đoạn {start_m} đến {end_m} năm {yr if mo+3<=12 else yr+1}</div>',
            unsafe_allow_html=True,
        )

        if crop == "Lúa":
            gs = growth_stages_lua
            diseases = [
                ("Rầy",          {d: min(3, decade_risks.get("Lúa",{}).get(d,1)) for d in active_decades}),
                ("Sâu cuốn lá",  {d: min(3, max(1, 2 if df_decadal is not None and not df_decadal.empty else 1)) for d in active_decades}),
                ("Đục thân",     {d: 1 for d in active_decades}),
                ("Đạo ôn",       {d: min(3, decade_risks.get("Lúa",{}).get(d,1)) for d in active_decades}),
                ("Nấm cổ bông",  {d: 1 for d in active_decades}),
                ("Khô vằn",      {d: 1 for d in active_decades}),
                ("Rầy nâu",      {d: min(3, decade_risks.get("Lúa",{}).get(d,1)) for d in active_decades}),
            ]
        elif crop == "Rau":
            gs = growth_stages_rau
            diseases = [
                ("Sâu xanh",      {d: 1 for d in active_decades}),
                ("Sâu tơ",        {d: 1 for d in active_decades}),
                ("Rệp",           {d: 1 for d in active_decades}),
                ("Bọ nhảy",       {d: 1 for d in active_decades}),
                ("Bệnh thối gốc", {d: min(3, decade_risks.get("Rau",{}).get(d,1)) for d in active_decades}),
                ("Sương mai",     {d: min(3, decade_risks.get("Rau",{}).get(d,1)) for d in active_decades}),
            ]
        elif crop == "Lợn":
            gs = None
            diseases = [
                ("Dịch tả lợn Châu Phi",   {d: 1 for d in active_decades}),
                ("Dịch tả lợn cổ điển",    {d: 1 for d in active_decades}),
                ("Viêm phổi dính sườn",    {d: 1 for d in active_decades}),
                ("Suyễn lợn",              {d: 1 for d in active_decades}),
                ("Tai xanh (PRRS)",        {d: 1 for d in active_decades}),
                ("Tiêu chảy do E. coli",   {d: min(3, decade_risks.get("Lợn",{}).get(d,1)) for d in active_decades}),
                ("Đóng dấu lợn",           {d: min(3, decade_risks.get("Lợn",{}).get(d,1)) for d in active_decades}),
                ("Lở mồm long móng",       {d: 1 for d in active_decades}),
                ("Tụ huyết trùng lợn",     {d: min(3, decade_risks.get("Lợn",{}).get(d,1)) for d in active_decades}),
            ]
        else:  # Gà
            gs = None
            diseases = [
                ("Hen gà",                    {d: 1 for d in active_decades}),
                ("Cúm gia cầm độc lực cao",   {d: 1 for d in active_decades}),
                ("Cầu trùng gà",              {d: min(3, decade_risks.get("Gà",{}).get(d,1)) for d in active_decades}),
                ("Viêm ruột hoại tử",         {d: 1 for d in active_decades}),
                ("Newcastle",                 {d: 1 for d in active_decades}),
                ("Tụ huyết trùng gia cầm",    {d: min(3, decade_risks.get("Gà",{}).get(d,1)) for d in active_decades}),
                ("Ký sinh trùng đường máu",   {d: min(3, decade_risks.get("Gà",{}).get(d,1)) for d in active_decades}),
                ("Đậu gà",                    {d: min(3, decade_risks.get("Gà",{}).get(d,1)) for d in active_decades}),
            ]

        html_risk = render_risk_table(crop, active_decades, decade_risks, gs, diseases)
        st.markdown(html_risk, unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:11px; margin:-6px 0 10px 0;">'
            '<span style="background:#c8f7c5; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Thấp</span>'
            '<span style="background:#fff176; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Trung bình (TB)</span>'
            '<span style="background:#ff8a65; padding:2px 8px; margin-right:6px; border-radius:3px;">■ Cao</span>'
            '<span style="background:#f0f0f0; padding:2px 8px; border-radius:3px;">■ Không áp dụng</span>'
            '</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# CÁC TRANG
# ══════════════════════════════════════════════════════════════════════════════

def page_tong_quan():
    st.title("🌾 Công cụ quản lý rủi ro khí hậu đối với cây trồng và vật nuôi tỉnh Quảng Ninh")
    st.markdown(
        "Hệ thống hỗ trợ tạo **bản tin cảnh báo khí hậu** cho các xã tại Quảng Ninh, "
        "bao gồm đánh giá rủi ro cho **Lúa, Rau, Lợn, Gà** theo từng kỳ tháng."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏘️ Số xã", str(len(COMMUNE_CROPS)))
    c2.metric("🌱 Đối tượng nông nghiệp", "4")
    c3.metric("📅 Kỳ dự báo", "3 tháng")
    c4.metric("📄 Bản tin đã tạo", "0")


def page_du_bao():
    st.markdown('<div class="module-header">🔄 Dự báo khí hậu mùa</div>',
                unsafe_allow_html=True)

    with st.spinner("⏳ Đang tải shapefile …"):
        gdf_all_tinh, gdf_tinh_qn, gdf_xa = load_shapefiles()

    if gdf_all_tinh is None and gdf_xa is None:
        st.warning("⚠️ Không tải được shapefile – bản đồ sẽ không có ranh giới.")

    boundary_data = build_boundary_traces_cached(gdf_all_tinh, gdf_tinh_qn, gdf_xa)

    with st.spinner("🔍 Kiểm tra dữ liệu mới nhất …"):
        periods = fetch_available_periods()
    if not periods:
        st.error("❌ Không kết nối được server hoặc chưa có dữ liệu.")
        return

    periods_desc = list(reversed(periods))
    yr_mo_labels = [f"{p[:4]}/{p[4:]}" for p in periods_desc]

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sel_idx = st.selectbox(
            "📅 Kỳ dự báo:", range(len(periods_desc)),
            format_func=lambda i: yr_mo_labels[i],
            help="Tự động cập nhật khi server có thư mục mới",
        )
        sel_period = periods_desc[sel_idx]

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = []
    for d in range(1, 4):
        m2 = mo + d
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        month_labels.append(f"Tháng {m2:02d}/{y2}")

    with col2:
        month_idx = st.selectbox("🗓️ Hạn dự báo:", range(3),
                                  format_func=lambda i: month_labels[i])
    with col3:
        show_xa = st.toggle("🗺️ Hiển thị lớp xã", value=False)

    st.markdown("---")
    tab_c, tab_e = st.tabs(["🌡️ Chuẩn sai dự báo khí hậu",
                             "⚠️ Chuẩn sai dự báo cực đoan"])
    with tab_c:
        _map_fragment("c", CLIMATE_VARS, sel_period, month_idx,
                      boundary_data, month_labels, show_xa)
    with tab_e:
        _map_fragment("e", EXTREME_VARS, sel_period, month_idx,
                      boundary_data, month_labels, show_xa)


def page_ban_tin_xa():
    st.markdown('<div class="module-header">📋 Bản tin cảnh báo rủi ro khí hậu</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([2, 3])

    with col1:
        with st.spinner("🔍 Kiểm tra dữ liệu …"):
            periods = fetch_available_periods()
        if not periods:
            st.error("❌ Không kết nối được server."); return

        periods_desc = list(reversed(periods))
        sel_idx = st.selectbox(
            "📅 Kỳ dự báo:", range(len(periods_desc)),
            format_func=lambda i: f"{periods_desc[i][:4]}/{periods_desc[i][4:]}",
        )
        sel_period = periods_desc[sel_idx]
        commune_list = list(COMMUNE_CROPS.keys())
        sel_commune  = st.selectbox("🏘️ Chọn xã:", commune_list)

    yr, mo = int(sel_period[:4]), int(sel_period[4:])
    month_labels = []
    for d in range(1, 4):
        m2 = mo + d
        y2 = yr + (m2 - 1) // 12
        m2 = ((m2 - 1) % 12) + 1
        month_labels.append(f"Tháng {m2:02d}/{y2}")

    with col2:
        st.markdown("**📅 Kỳ dự báo:**")
        st.info(f"Tháng {month_labels[0].split('Tháng ')[1]} → {month_labels[-1].split('Tháng ')[1]}")
        st.markdown(f"**🌾 Đối tượng:** {', '.join(COMMUNE_CROPS.get(sel_commune, []))}")

    st.markdown("---")

    crops = COMMUNE_CROPS.get(sel_commune, [])

    with st.spinner("📥 Đang tải dữ liệu ERA5 TBNN …"):
        df_r, df_t = load_era5_data()
    with st.spinner("📥 Đang tải dự báo theo thập …"):
        df_decadal = load_member_decadal(sel_period)
    with st.spinner("📥 Đang tải dự báo xác suất (XSHC/XSCC/XSVC) …"):
        xacsuat_data = load_xacsuat_for_commune(sel_period, sel_commune)
    with st.spinner("⏳ Đang tải shapefile …"):
        _, _, gdf_xa = load_shapefiles()

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
    st.markdown('<div class="module-header">💾 Bản tin đã lưu</div>', unsafe_allow_html=True)
    st.info("Module đang phát triển.")


def page_export():
    st.markdown('<div class="module-header">📤 Export bản tin</div>', unsafe_allow_html=True)
    st.info("Module đang phát triển.")


def page_phan_hoi():
    st.markdown('<div class="module-header">💬 Phản hồi</div>', unsafe_allow_html=True)
    st.info("Module đang phát triển.")


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR & ĐIỀU HƯỚNG
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🌾 Bản tin Khí hậu")
    st.markdown("**Quảng Ninh – Nông nghiệp**")
    st.markdown("---")
    menu = st.radio("📌 Chọn module:", [
        "🏠 Tổng quan",
        "🔄 Dự báo khí hậu mùa",
        "📋 Bản tin cảnh báo rủi ro khí hậu",
        "💾 Bản tin đã lưu",
        "📤 Export bản tin",
        "💬 Phản hồi",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("Phòng Nghiên cứu Khí tượng nông nghiệp và Dịch vụ khí hậu")
    st.markdown("Viện Khoa học Khí tượng Thủy văn Môi trường và Biển")
    st.markdown("---")
    st.markdown("*Phiên bản 1.4.0 – 06/2026*")

if   menu == "🏠 Tổng quan":                          page_tong_quan()
elif menu == "🔄 Dự báo khí hậu mùa":                page_du_bao()
elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":   page_ban_tin_xa()
elif menu == "💾 Bản tin đã lưu":                     page_ban_tin_da_luu()
elif menu == "📤 Export bản tin":                     page_export()
elif menu == "💬 Phản hồi":                           page_phan_hoi()
