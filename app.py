# -*- coding: utf-8 -*-
"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
THAY ĐỔI v1.2.0 – TỐI ƯU HIỆU NĂNG STREAMLIT CLOUD:
  [PERF-1] Shapefile geometry → pre-convert sang Plotly traces 1 lần, cache vĩnh viễn
  [PERF-2] Ranh giới tỉnh/xã dùng Scattergl (WebGL) thay Scatter → browser nhẹ hơn nhiều
  [PERF-3] st.fragment cho map panel → chỉ re-render vùng bản đồ, không reload toàn trang
  [PERF-4] Grid nội suy 150×150 (thay 300×300), cache IDW+mask
  [FIX]    Tên xã UTF-8 đúng tiếng Việt
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
import os, re, tempfile, warnings
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
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e8f4f8; border-radius: 6px 6px 0 0;
        padding: 8px 16px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background-color: #1e3a5f !important; color: white !important; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e3a5f 0%, #2d3748 100%); }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL   = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
SHP_QN_URL = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"

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
# LOAD SHAPEFILE – cache vĩnh viễn suốt session (st.cache_resource)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_shapefiles():
    """
    Tải shapefile 1 lần duy nhất trong toàn bộ session.
    Trả về (gdf_all_tinh, gdf_tinh_qn, gdf_xa).
    """
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
        p = _download_shp("QN_XA_FINAL")
        if p:
            gdf_xa = _read_safe(p)
    except Exception:
        pass

    return gdf_all_tinh, gdf_tinh_qn, gdf_xa


# ══════════════════════════════════════════════════════════════════════════════
# [PERF-1] PRE-CONVERT geometry → Plotly traces, cache vĩnh viễn
#           Mỗi GDF chỉ convert 1 lần trong toàn bộ session
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def build_boundary_traces_cached(_gdf_all_tinh, _gdf_tinh_qn, _gdf_xa):
    """
    Trả về dict chứa sẵn x/y arrays cho ranh giới tỉnh và xã.
    Dùng Scattergl (WebGL) thay Scatter → browser render nhanh gấp 5-10×.
    Cache_resource: object không bao giờ bị serialize lại.
    """

    def _geom_to_xy(gdf):
        """Gộp toàn bộ polygon trong GDF thành 1 mảng x/y duy nhất (dùng None làm separator)."""
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
        """Centroid + tên xã (đã fix encoding)."""
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

    # Tỉnh lân cận (đường mỏng)
    if _gdf_all_tinh is not None and not _gdf_all_tinh.empty:
        result["tinh_x"], result["tinh_y"] = _geom_to_xy(_gdf_all_tinh)

    # Ranh giới QN đậm
    if _gdf_tinh_qn is not None and not _gdf_tinh_qn.empty:
        result["qn_x"], result["qn_y"] = _geom_to_xy(_gdf_tinh_qn)
        result["mask_wkt"] = _gdf_tinh_qn.unary_union.wkt
        result["bounds"]   = tuple(_gdf_tinh_qn.total_bounds)   # (minx,miny,maxx,maxy)

    # Ranh giới xã
    if _gdf_xa is not None and not _gdf_xa.empty:
        result["xa_x"], result["xa_y"] = _geom_to_xy(_gdf_xa)
        result["xa_lx"], result["xa_ly"], result["xa_texts"] = _xa_labels(_gdf_xa)
        if "bounds" not in result:
            result["bounds"]   = tuple(_gdf_xa.total_bounds)
            result["mask_wkt"] = _gdf_xa.unary_union.wkt

    return result


# ══════════════════════════════════════════════════════════════════════════════
# DỮ LIỆU NETCDF
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
def download_nc(period: str, var_prefix: str):
    url = f"{BASE_URL}{period}/{var_prefix}.{period}.nc"
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
def _compute_grid(lons_t: tuple, lats_t: tuple, vals_t: tuple,
                  minx, miny, maxx, maxy, mask_wkt: str,
                  GRID_N: int = 400, SIGMA: float = 1.0):
    """
    IDW + smooth + mask – cache_data → gọi lại cùng tham số trả về ngay.
    GRID_N=150: 22500 điểm (thay vì 90000), đủ mịn cho vùng Quảng Ninh.
    """
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


# ══════════════════════════════════════════════════════════════════════════════
# COLORMAP
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def _mpl_to_plotly(cmap_name: str, n: int = 128) -> list:
    """n=128 thay 256 – giảm nửa dữ liệu gửi browser, mắt thường không phân biệt được."""
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap(cmap_name)
    pos = np.linspace(0, 1, n)
    return [[p, f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"]
            for p, (r, g, b, _) in zip(pos, [cmap(v) for v in pos])]


# ══════════════════════════════════════════════════════════════════════════════
# BUILD FIGURE – dùng traces đã pre-build sẵn từ boundary_data
# ══════════════════════════════════════════════════════════════════════════════

def build_figure(lons, lats, vals, meta: dict, title: str,
                 boundary_data: dict, show_xa: bool):
    """
    Xây dựng Plotly figure.
    boundary_data: dict từ build_boundary_traces_cached() – đã có sẵn x/y arrays.
    Dùng Scattergl (WebGL) cho ranh giới → render browser cực nhanh.
    """
    bounds = boundary_data.get("bounds")
    if bounds:
        minx, miny, maxx, maxy = bounds
    else:
        minx, miny, maxx, maxy = 106.3, 20.6, 108.3, 21.8

    BUF = 0.12
    plot_minx, plot_miny = minx - BUF, miny - BUF
    plot_maxx, plot_maxy = maxx + BUF, maxy + BUF

    # Lọc điểm dữ liệu
    buf_data = 1.5
    ok = ((lons >= minx - buf_data) & (lons <= maxx + buf_data) &
          (lats >= miny - buf_data) & (lats <= maxy + buf_data))
    xi, yi, zi = lons[ok], lats[ok], vals[ok]
    if xi.size == 0:
        return None, "Không có điểm dữ liệu trong vùng Quảng Ninh"

    # IDW + mask (cached)
    mask_wkt = boundary_data.get("mask_wkt", "")
    gx_vec, gy_vec, gv_masked = _compute_grid(
        tuple(xi.tolist()), tuple(yi.tolist()), tuple(zi.tolist()),
        float(minx), float(miny), float(maxx), float(maxy), mask_wkt,
    )

    # Clip
    levels = sorted(meta.get("levels", list(range(-5, 6))))
    vmin, vmax = levels[0], levels[-1]
    gv_display = np.where(np.isnan(gv_masked), np.nan,
                           np.clip(gv_masked, vmin, vmax))

    colorscale = _mpl_to_plotly(meta.get("cmap", "RdBu_r"))
    unit = meta.get("unit", "")

    fig = go.Figure()

    # ── Ranh giới tỉnh lân cận (Scattergl = WebGL, 1 trace duy nhất) ──
    if "tinh_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["tinh_x"], y=boundary_data["tinh_y"],
            mode="lines",
            line=dict(color="#aab0b8", width=0.5),
            hoverinfo="skip", showlegend=False, name="",
        ))

    # ── Filled contour nội suy ──
    fig.add_trace(go.Contour(
        z=gv_display, x=gx_vec, y=gy_vec,
        colorscale=colorscale, zmin=vmin, zmax=vmax,
        autocontour=False,
        contours=dict(
            start=vmin, end=vmax,
            size=float(np.min(np.diff(levels))) if len(levels) > 1 else 1.0,
            coloring="fill", showlines=False,
        ),
        colorbar=dict(
            title=dict(text=f"Chuẩn sai ({unit})", side="right",
                       font=dict(size=12, family="Arial, sans-serif")),
            tickvals=levels, ticktext=[str(v) for v in levels],
            tickfont=dict(size=10), thickness=16, len=0.75,
            outlinewidth=1, outlinecolor="#aaa",
        ),
        opacity=0.90, connectgaps=False,
        hovertemplate=(
            "Lon: %{x:.3f}°E<br>Lat: %{y:.3f}°N<br>"
            f"Giá trị: %{{z:.2f}} {unit}<extra></extra>"
        ),
        name="Nội suy", showscale=True,
    ))

    # ── Viền QN đậm (Scattergl) ──
    if "qn_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["qn_x"], y=boundary_data["qn_y"],
            mode="lines",
            line=dict(color="#111111", width=2.2),
            hoverinfo="skip", showlegend=True, name="Ranh giới Quảng Ninh",
        ))

    # ── Ranh giới xã (Scattergl, bật/tắt qua legend) ──
    xa_visible = True if show_xa else "legendonly"
    if "xa_x" in boundary_data:
        fig.add_trace(go.Scattergl(
            x=boundary_data["xa_x"], y=boundary_data["xa_y"],
            mode="lines",
            line=dict(color="#e07b00", width=1.1, dash="dot"),
            hoverinfo="skip",
            visible=xa_visible,
            showlegend=True, name="Ranh giới xã", legendgroup="xa_border",
        ))

    # ── Nhãn tên xã (Scatter thường – text mode, số điểm ít nên OK) ──
    if "xa_lx" in boundary_data and boundary_data["xa_texts"]:
        lbl = go.Scatter(
            x=boundary_data["xa_lx"], y=boundary_data["xa_ly"],
            mode="text", text=boundary_data["xa_texts"],
            textfont=dict(size=9, color="#111111",
                          family="Arial Unicode MS, Arial, sans-serif"),
            textposition="middle center",
            hoverinfo="skip",
            visible=xa_visible,
            showlegend=True, name="Tên xã", legendgroup="xa_label",
        )
        fig.add_trace(lbl)

    # ── Layout cố định ──
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, family="Arial, sans-serif"),
                   x=0.5, xanchor="center"),
        xaxis=dict(
            title="Kinh độ (°E)", range=[plot_minx, plot_maxx],
            fixedrange=True, tickformat=".2f",
            scaleanchor="y", scaleratio=1, constrain="domain",
            showgrid=True, gridcolor="rgba(180,180,180,0.3)", gridwidth=0.5,
        ),
        yaxis=dict(
            title="Vĩ độ (°N)", range=[plot_miny, plot_maxy],
            fixedrange=True, tickformat=".2f",
            showgrid=True, gridcolor="rgba(180,180,180,0.3)", gridwidth=0.5,
        ),
        legend=dict(x=0.01, y=0.01, bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#aaa", borderwidth=1, font=dict(size=10)),
        margin=dict(l=60, r=20, t=50, b=50),
        height=680,
        plot_bgcolor="white", paper_bgcolor="white",
        hovermode="closest", dragmode=False,
        modebar_remove=[
            "zoom", "pan", "zoomIn2d", "zoomOut2d", "resetScale2d",
            "lasso2d", "select2d", "autoScale2d",
            "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines",
        ],
    )
    return fig, None


# ══════════════════════════════════════════════════════════════════════════════
# RENDER + DISPLAY – dùng @st.fragment để chỉ re-render vùng bản đồ
# ══════════════════════════════════════════════════════════════════════════════

def render_var_panel(var_prefix, meta, period, month_idx,
                     boundary_data, month_labels, state_key, show_xa):
    with st.spinner(f"⏳ Đang tải {meta['label']} …"):
        nc_bytes = download_nc(period, var_prefix)
    if nc_bytes is None:
        st.session_state[state_key] = {
            "error": f"Không tải được file NC: {var_prefix}.{period}.nc"}
        return

    with st.spinner("🔄 Đang đọc dữ liệu …"):
        lons, lats, vals, err = load_nc_data(nc_bytes, month_idx)
    if err:
        st.session_state[state_key] = {"error": f"Lỗi đọc dữ liệu: {err}"}
        return

    month_str = month_labels[month_idx] if month_idx < len(month_labels) else f"Tháng +{month_idx+1}"
    title = f"Chuẩn sai {meta['label']} – {month_str} (Kỳ {period[:4]}/{period[4:]})"

    with st.spinner("🗺️ Đang nội suy và vẽ bản đồ …"):
        fig, err2 = build_figure(lons, lats, vals, meta, title,
                                  boundary_data, show_xa)
    if err2:
        st.session_state[state_key] = {"error": err2}
        return

    st.session_state[state_key] = {
        "fig":      fig,
        "filename": f"chuan_sai_{var_prefix.replace('.','_')}_{period}_t{month_idx+1}.png",
        "error":    None,
    }


def display_panel(state_key: str):
    result = st.session_state.get(state_key)
    if result is None:
        return
    if result.get("error"):
        st.error(f"❌ {result['error']}")
        return
    st.plotly_chart(
        result["fig"], use_container_width=True,
        config={
            "scrollZoom": False,
            "displayModeBar": True,
            "modeBarButtonsToRemove": [
                "zoom2d","pan2d","zoomIn2d","zoomOut2d",
                "autoScale2d","resetScale2d","lasso2d","select2d",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": result["filename"],
                "scale": 2,
            },
        },
    )
    st.caption("💡 Hover vào bản đồ để xem giá trị. Bấm legend để ẩn/hiện lớp xã.")


# ══════════════════════════════════════════════════════════════════════════════
# [PERF-3] st.fragment – map panel chỉ re-render nội bộ, không reload toàn trang
# ══════════════════════════════════════════════════════════════════════════════

@st.fragment
def _map_fragment(tab_key, var_dict, period, month_idx,
                  boundary_data, month_labels, show_xa):
    """
    Fragment độc lập: mọi tương tác bên trong (chọn biến, bấm nút)
    chỉ re-run đoạn này, KHÔNG làm reload toàn bộ page.
    """
    state_key = f"map_{tab_key}"
    sel = st.selectbox(
        "Chọn biến:", list(var_dict.keys()),
        format_func=lambda k: var_dict[k]["label"],
        key=f"sel_{tab_key}",
    )
    if st.button("🗺️ Vẽ bản đồ", key=f"btn_{tab_key}", type="primary"):
        render_var_panel(sel, var_dict[sel], period, month_idx,
                         boundary_data, month_labels, state_key, show_xa)
    display_panel(state_key)


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
    c1.metric("🏘️ Số xã", "30")
    c2.metric("🌱 Đối tượng nông nghiệp", "4")
    c3.metric("📅 Kỳ dự báo", "3 tháng")
    c4.metric("📄 Bản tin đã tạo", "0")


def page_du_bao():
    st.markdown('<div class="module-header">🔄 Dự báo khí hậu mùa</div>',
                unsafe_allow_html=True)

    # Load shapefile (cache_resource → chỉ tải 1 lần)
    with st.spinner("⏳ Đang tải shapefile …"):
        gdf_all_tinh, gdf_tinh_qn, gdf_xa = load_shapefiles()

    if gdf_all_tinh is None and gdf_xa is None:
        st.warning("⚠️ Không tải được shapefile – bản đồ sẽ không có ranh giới.")

    # Pre-build traces 1 lần (cache_resource → không bao giờ rebuild lại)
    boundary_data = build_boundary_traces_cached(gdf_all_tinh, gdf_tinh_qn, gdf_xa)

    # Lấy danh sách kỳ
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
        month_idx = st.selectbox(
            "🗓️ Hạn dự báo:", range(3),
            format_func=lambda i: month_labels[i],
            help="3 tháng tiếp theo sau kỳ phát bản tin",
        )

    with col3:
        show_xa = st.toggle(
            "🗺️ Hiển thị lớp xã", value=False,
            help="Bật để xem ranh giới và tên các xã trong vùng nghiên cứu",
        )

    st.markdown("---")

    tab_c, tab_e = st.tabs([
        "🌡️ Chuẩn sai dự báo khí hậu",
        "⚠️ Chuẩn sai dự báo cực đoan",
    ])

    with tab_c:
        _map_fragment("c", CLIMATE_VARS, sel_period, month_idx,
                      boundary_data, month_labels, show_xa)

    with tab_e:
        _map_fragment("e", EXTREME_VARS, sel_period, month_idx,
                      boundary_data, month_labels, show_xa)


def page_ban_tin_xa():
    st.markdown('<div class="module-header">📋 Bản tin cảnh báo rủi ro khí hậu</div>',
                unsafe_allow_html=True)
    st.info("Module đang phát triển.")


def page_ban_tin_da_luu():
    st.markdown('<div class="module-header">💾 Bản tin đã lưu</div>',
                unsafe_allow_html=True)
    st.info("Module đang phát triển.")


def page_export():
    st.markdown('<div class="module-header">📤 Export bản tin</div>',
                unsafe_allow_html=True)
    st.info("Module đang phát triển.")


def page_phan_hoi():
    st.markdown('<div class="module-header">💬 Phản hồi</div>',
                unsafe_allow_html=True)
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
    st.markdown("*Phiên bản 1.2.0 – 06/2026*")

# ── Router ──
if   menu == "🏠 Tổng quan":                          page_tong_quan()
elif menu == "🔄 Dự báo khí hậu mùa":                page_du_bao()
elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":   page_ban_tin_xa()
elif menu == "💾 Bản tin đã lưu":                     page_ban_tin_da_luu()
elif menu == "📤 Export bản tin":                      page_export()
elif menu == "💬 Phản hồi":                            page_phan_hoi()
