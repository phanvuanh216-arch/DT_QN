"""
modules/du_bao_tu_dong.py
Module: Dự báo khí hậu mùa – được gọi từ app.py qua du_bao_tu_dong.render()

Gồm 2 sub-module (st.tabs):
  1. Chuẩn sai dự báo khí hậu  – T2m, Tx, Tm, R, RH2m
  2. Chuẩn sai dự báo cực đoan – CDD, CWD, Evap, FD13, FD15,
                                  Rx1day, Rx5day, SU35, SU37, SU39

Bản đồ: nội suy IDW + Gaussian smooth + mask vùng Quảng Ninh.
Có toggle bật/tắt: ranh giới tỉnh, ranh giới xã, tên xã, tên tỉnh.
"""

from __future__ import annotations
import os
import re
import tempfile
from io import BytesIO

import numpy as np
import requests
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import BoundaryNorm

import netCDF4 as nc
import geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

# ─── Đường dẫn dữ liệu ────────────────────────────────────────────────────────
DATA_DIR = "/imhen-data/share-imhen/phonglv/Detai_QuangNinh/domain_d02"

# ─── Shapefile GitHub ─────────────────────────────────────────────────────────
_SHP_RAW  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"
_SHP_EXTS = [".shp", ".dbf", ".shx", ".prj", ".cpg"]

# Shapefile cấp xã – chứa ranh giới xã + tên xã + tên tỉnh
_SHP_XA   = "Quang_Ninh_Xa"   # → Quang_Ninh_Xa.shp  (cột: ten_xa, ten_tinh hoặc tương tự)

# ─── Bbox Quảng Ninh ─────────────────────────────────────────────────────────
QN_MINX, QN_MAXX = 106.30, 108.45
QN_MINY, QN_MAXY = 20.55,  22.05

# ─── Lưới nội suy ────────────────────────────────────────────────────────────
GRID_N   = 600      # điểm lưới mỗi chiều
IDW_K    = 12       # số điểm lân cận IDW
IDW_PWR  = 3.0      # lũy thừa khoảng cách
SIGMA    = 1.2      # Gaussian smooth sigma

# ─── Danh sách biến ───────────────────────────────────────────────────────────
VARS_CLIMATE: dict[str, dict] = {
    "ano.T2m":  {"label": "Nhiệt độ TB (T₂ₘ)",        "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.Tx":   {"label": "Nhiệt độ tối cao (Tₓ)",     "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.Tm":   {"label": "Nhiệt độ tối thấp (Tₘ)",    "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.R":    {"label": "Lượng mưa (R)",              "unit": "mm",  "cmap": "BrBG",    "vmin": -150, "vmax": 150},
    "ano.RH2m": {"label": "Độ ẩm tương đối (RH₂ₘ)",   "unit": "%",   "cmap": "BrBG",    "vmin": -10,  "vmax": 10},
}

VARS_EXTREME: dict[str, dict] = {
    "ano.CDD":    {"label": "Ngày khô liên tiếp (CDD)",           "unit": "ngày", "cmap": "YlOrRd", "vmin": -10,  "vmax": 10},
    "ano.CWD":    {"label": "Ngày mưa liên tiếp (CWD)",           "unit": "ngày", "cmap": "YlGnBu", "vmin": -5,   "vmax": 5},
    "ano.Evap":   {"label": "Bốc thoát hơi (Evap)",               "unit": "mm",   "cmap": "BrBG",   "vmin": -50,  "vmax": 50},
    "ano.FD13":   {"label": "Ngày rét đậm ≤13 °C (FD13)",         "unit": "ngày", "cmap": "Blues",  "vmin": -5,   "vmax": 5},
    "ano.FD15":   {"label": "Ngày rét hại ≤15 °C (FD15)",         "unit": "ngày", "cmap": "PuBu",   "vmin": -5,   "vmax": 5},
    "ano.Rx1day": {"label": "Mưa 1 ngày lớn nhất (Rx1day)",       "unit": "mm",   "cmap": "BuPu",   "vmin": -50,  "vmax": 50},
    "ano.Rx5day": {"label": "Mưa 5 ngày lớn nhất (Rx5day)",       "unit": "mm",   "cmap": "BuPu",   "vmin": -100, "vmax": 100},
    "ano.SU35":   {"label": "Ngày nắng nóng ≥35 °C (SU35)",       "unit": "ngày", "cmap": "YlOrRd", "vmin": -10,  "vmax": 10},
    "ano.SU37":   {"label": "Ngày nắng nóng gg ≥37 °C (SU37)",    "unit": "ngày", "cmap": "OrRd",   "vmin": -5,   "vmax": 5},
    "ano.SU39":   {"label": "Ngày nắng nóng đb ≥39 °C (SU39)",    "unit": "ngày", "cmap": "Reds",   "vmin": -3,   "vmax": 3},
}

# ==============================================================================
# SHAPEFILE
# ==============================================================================
@st.cache_resource(show_spinner="Đang tải shapefile Quảng Ninh…")
def _load_shp_xa() -> gpd.GeoDataFrame | None:
    """Tải shapefile cấp xã từ GitHub, trả về GeoDataFrame EPSG:4326."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ok = True
            for ext in _SHP_EXTS:
                fname = _SHP_XA + ext
                url   = _SHP_RAW + fname
                r = requests.get(url, timeout=20)
                if r.status_code == 200:
                    with open(os.path.join(tmp, fname), "wb") as f:
                        f.write(r.content)
                elif ext in (".shp", ".dbf", ".shx"):
                    ok = False
                    break
            if not ok:
                return None
            shp = os.path.join(tmp, _SHP_XA + ".shp")
            if not os.path.exists(shp):
                return None
            gdf = gpd.read_file(shp)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            return gdf
    except Exception as e:
        st.warning(f"⚠️ Không tải được shapefile: {e}")
        return None


def _col_name(gdf: gpd.GeoDataFrame, candidates: list[str]) -> str | None:
    """Trả về tên cột đầu tiên tìm thấy trong GeoDataFrame (không phân biệt hoa/thường)."""
    low = {c.lower(): c for c in gdf.columns}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None


# ==============================================================================
# QUÉT KỲ DỮ LIỆU
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _get_periods() -> list[str]:
    out = []
    try:
        if os.path.isdir(DATA_DIR):
            for e in os.scandir(DATA_DIR):
                if e.is_dir() and re.match(r"^\d{6}$", e.name):
                    out.append(e.name)
    except Exception:
        pass
    out.sort(reverse=True)
    return out


def _period_label(p: str) -> str:
    return f"Tháng {int(p[4:]):02d}/{p[:4]}"


# ==============================================================================
# ĐỌC NETCDF
# ==============================================================================
@st.cache_data(ttl=600, show_spinner="Đang đọc dữ liệu…")
def _read_nc(path: str, var_key: str):
    """
    Trả về (data3d, lon1d, lat1d, time_labels).
    data3d shape: (≤3, ny, nx) – dữ liệu thô chưa nội suy.
    """
    try:
        ds  = nc.Dataset(path)
        short = var_key.split(".")[-1]

        if short in ds.variables:
            raw = ds.variables[short][:]
        else:
            skip  = {"lon", "lat", "time", "longitude", "latitude"}
            cands = [v for v in ds.variables if v not in skip]
            if not cands:
                ds.close()
                return None, None, None, None
            raw = ds.variables[cands[0]][:]

        lon_k = "lon"       if "lon"       in ds.variables else "longitude"
        lat_k = "lat"       if "lat"       in ds.variables else "latitude"
        lon   = np.array(ds.variables[lon_k][:])
        lat   = np.array(ds.variables[lat_k][:])

        tv = ds.variables.get("time")
        if tv is not None:
            try:
                cal    = getattr(tv, "calendar", "gregorian")
                tms    = nc.num2date(tv[:], tv.units, calendar=cal)
                tlabels = [f"{t.year}-{t.month:02d}" for t in tms]
            except Exception:
                tlabels = [f"Bước {i+1}" for i in range(raw.shape[0])]
        else:
            tlabels = [f"Bước {i+1}" for i in range(raw.shape[0])]

        ds.close()
        data    = np.ma.filled(np.array(raw, dtype=float), np.nan)[:3]
        tlabels = tlabels[:3]
        return data, lon, lat, tlabels

    except Exception as e:
        st.error(f"Lỗi đọc NetCDF: {e}")
        return None, None, None, None


# ==============================================================================
# NỘI SUY IDW + GAUSSIAN MASK VÀO VÙNG QUẢNG NINH
# ==============================================================================
def _idw_knn(xi, yi, zi, query_xy, k=12, power=3.0, eps=1e-12):
    """IDW với KD-Tree (lấy từ code gốc tham chiếu)."""
    tree  = cKDTree(np.column_stack([xi, yi]))
    dists, idxs = tree.query(query_xy, k=min(k, xi.size))
    if dists.ndim == 1:
        dists, idxs = dists[:, None], idxs[:, None]

    out   = np.empty(dists.shape[0], dtype=float)
    exact = dists <= eps

    for r in np.where(exact.any(axis=1))[0]:
        out[r] = zi[idxs[r, np.where(exact[r])[0][0]]]

    rest = ~exact.any(axis=1)
    if np.any(rest):
        d, nn = dists[rest], idxs[rest]
        w     = 1.0 / np.maximum(d, eps) ** power
        out[rest] = (w * zi[nn]).sum(axis=1) / w.sum(axis=1)
    return out


@st.cache_data(ttl=600, show_spinner="Đang nội suy dữ liệu vào lưới Quảng Ninh…")
def _interpolate_to_qn(
    data2d_flat: np.ndarray,   # giá trị 1-D (đã flatten, chỉ điểm trong bbox QN)
    lon_flat: np.ndarray,       # kinh độ 1-D
    lat_flat: np.ndarray,       # vĩ độ 1-D
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Nội suy IDW lên lưới đều Quảng Ninh rồi làm mịn Gaussian.
    Trả về (gx, gy, gv_smooth) – lưới 2-D.
    """
    gx, gy = np.meshgrid(
        np.linspace(QN_MINX, QN_MAXX, GRID_N),
        np.linspace(QN_MINY, QN_MAXY, GRID_N),
    )
    query_xy = np.column_stack([gx.ravel(), gy.ravel()])

    # Loại NaN
    mask_valid = ~np.isnan(data2d_flat)
    xi  = lon_flat[mask_valid]
    yi  = lat_flat[mask_valid]
    zi  = data2d_flat[mask_valid]

    if zi.size == 0:
        return gx, gy, np.full(gx.shape, np.nan)

    gv = _idw_knn(xi, yi, zi, query_xy, k=IDW_K, power=IDW_PWR).reshape(gx.shape)
    if SIGMA > 0:
        gv = gaussian_filter(gv, sigma=SIGMA)
    return gx, gy, gv


def _apply_shapefile_mask(
    gx: np.ndarray, gy: np.ndarray, gv: np.ndarray,
    gdf: gpd.GeoDataFrame
) -> np.ndarray:
    """Đặt NaN ngoài vùng shapefile (union tất cả polygon)."""
    try:
        shape_union = gdf.unary_union
        pshape  = prep(shape_union)
        pts     = np.column_stack([gx.ravel(), gy.ravel()])
        inside  = np.fromiter(
            (pshape.contains(Point(x, y)) for x, y in pts),
            count=pts.shape[0], dtype=bool
        ).reshape(gx.shape)
        return np.where(inside, gv, np.nan)
    except Exception:
        return gv  # fallback: không mask


# ==============================================================================
# VẼ BẢN ĐỒ (có toggle lớp)
# ==============================================================================
def _draw_map(
    gx, gy, gv_masked,
    gdf_xa: gpd.GeoDataFrame | None,
    meta: dict,
    group_title: str,
    time_label: str,
    # toggles
    show_tinh: bool   = True,
    show_xa: bool     = False,
    show_ten_xa: bool = False,
    show_ten_tinh: bool = False,
) -> plt.Figure:

    fig, ax = plt.subplots(figsize=(7, 6.5), dpi=140)
    fig.patch.set_facecolor("#f0f4f8")
    ax.set_facecolor("#dce8f0")

    vmin, vmax = meta["vmin"], meta["vmax"]
    cmap = plt.get_cmap(meta["cmap"])
    norm = (
        mcolors.TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
        if vmin < 0 < vmax
        else mcolors.Normalize(vmin=vmin, vmax=vmax)
    )

    # ── Hình nền nước biển ──────────────────────────────────────────────────
    ax.set_facecolor("#c8dff0")

    # ── Vùng đất (polygon tỉnh làm nền trắng) ────────────────────────────
    if gdf_xa is not None:
        try:
            gdf_xa.plot(ax=ax, color="#f5f5f0", edgecolor="none", zorder=1)
        except Exception:
            pass

    # ── Lớp nội suy (imshow) ────────────────────────────────────────────
    im = ax.imshow(
        gv_masked,
        extent=[QN_MINX, QN_MAXX, QN_MINY, QN_MAXY],
        cmap=cmap, norm=norm,
        interpolation="bilinear",
        origin="lower",
        alpha=0.88,
        zorder=2,
    )

    # ── Đường đẳng trị mịn ──────────────────────────────────────────────
    try:
        lvs = np.linspace(vmin, vmax, 11)
        valid_data = gv_masked[~np.isnan(gv_masked)]
        if valid_data.size > 0:
            ax.contour(gx, gy, gv_masked,
                       levels=lvs, colors="white",
                       linewidths=0.4, alpha=0.55, zorder=3)
    except Exception:
        pass

    # ── Ranh giới xã ────────────────────────────────────────────────────
    col_xa    = None
    col_tinh  = None
    if gdf_xa is not None:
        col_xa   = _col_name(gdf_xa, ["ten_xa",  "tenxa",  "TEN_XA",  "name_xa",  "NAME_XA"])
        col_tinh = _col_name(gdf_xa, ["ten_tinh","tentinh","TEN_TINH","name_tinh","NAME_TINH","tinh"])

        if show_xa:
            try:
                gdf_xa.boundary.plot(
                    ax=ax, edgecolor="#6b4226",
                    linewidth=0.5, linestyle="--", alpha=0.7, zorder=4
                )
            except Exception:
                pass

        # ── Tên xã ──────────────────────────────────────────────────────
        if show_ten_xa and col_xa:
            try:
                for _, row in gdf_xa.iterrows():
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    cx, cy = geom.centroid.x, geom.centroid.y
                    ten = str(row.get(col_xa, ""))
                    if not ten or ten == "nan":
                        continue
                    ax.text(
                        cx, cy, ten,
                        fontsize=4.5, ha="center", va="center",
                        color="#3b1a08", fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.08",
                                  facecolor="white", edgecolor="none",
                                  alpha=0.55),
                        zorder=7,
                    )
            except Exception:
                pass

        # ── Ranh giới tỉnh (dissolve từ lớp xã) ────────────────────────
        if show_tinh:
            try:
                if col_tinh:
                    gdf_tinh = gdf_xa.dissolve(by=col_tinh).reset_index()
                else:
                    gdf_tinh = gpd.GeoDataFrame(
                        geometry=[gdf_xa.unary_union], crs=gdf_xa.crs
                    )
                gdf_tinh.boundary.plot(
                    ax=ax, edgecolor="#1a1a2e",
                    linewidth=1.2, zorder=5
                )
            except Exception:
                pass

        # ── Tên tỉnh ────────────────────────────────────────────────────
        if show_ten_tinh and col_tinh:
            try:
                gdf_tinh2 = gdf_xa.dissolve(by=col_tinh).reset_index()
                for _, row in gdf_tinh2.iterrows():
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    cx, cy = geom.centroid.x, geom.centroid.y
                    ten = str(row.get(col_tinh, ""))
                    if not ten or ten == "nan":
                        continue
                    ax.text(
                        cx, cy, ten,
                        fontsize=7, ha="center", va="center",
                        color="#0d0d2b", fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.2",
                                  facecolor="white", edgecolor="#555",
                                  alpha=0.75),
                        zorder=8,
                    )
            except Exception:
                pass

    # ── Colorbar ────────────────────────────────────────────────────────
    cb = fig.colorbar(im, ax=ax, orientation="vertical",
                      fraction=0.028, pad=0.02, shrink=0.82, extend="both")
    cb.set_label(f"Chuẩn sai ({meta['unit']})", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    # ── Tiêu đề & trục ──────────────────────────────────────────────────
    ax.set_title(
        f"{group_title}\n{meta['label']}  –  {time_label}",
        fontsize=9, fontweight="bold", pad=8, color="#1e3a5f"
    )
    ax.set_xlabel("Kinh độ (°E)", fontsize=7)
    ax.set_ylabel("Vĩ độ (°N)", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_xlim(QN_MINX, QN_MAXX)
    ax.set_ylim(QN_MINY, QN_MAXY)
    ax.grid(linestyle="--", linewidth=0.3, color="gray", alpha=0.35, zorder=0)

    plt.tight_layout()
    return fig


# ==============================================================================
# PANEL CHUNG CHO MỖI NHÓM BIẾN
# ==============================================================================
def _render_group(
    var_dict: dict,
    period: str,
    gdf_xa: gpd.GeoDataFrame | None,
    group_title: str,
    tab_key: str,        # chuỗi duy nhất để tránh trùng widget key
) -> None:
    period_dir = os.path.join(DATA_DIR, period)

    # Lọc biến có file thực sự
    avail = {
        vk: vm for vk, vm in var_dict.items()
        if os.path.isfile(os.path.join(period_dir, f"{vk}.{period}.nc"))
    }

    if not avail:
        st.warning(
            f"⚠️ Chưa tìm thấy file dữ liệu trong:\n`{period_dir}`\n\n"
            "File cần có dạng: `ano.T2m.YYYYMM.nc`, `ano.R.YYYYMM.nc` …"
        )
        return

    # ── Hàng điều khiển chính ────────────────────────────────────────────
    col_var, col_step = st.columns([3, 1])

    with col_var:
        selected_var = st.selectbox(
            "🌡️ Chọn biến:",
            options=list(avail.keys()),
            format_func=lambda k: avail[k]["label"],
            key=f"var_{tab_key}_{period}",
        )

    nc_path              = os.path.join(period_dir, f"{selected_var}.{period}.nc")
    data3d, lon1d, lat1d, tlabels = _read_nc(nc_path, selected_var)

    if data3d is None:
        st.error("❌ Không đọc được dữ liệu.")
        return

    with col_step:
        step_opts    = {i: f"Tháng {tlabels[i]}" for i in range(len(tlabels))}
        selected_step = st.selectbox(
            "📅 Hạn dự báo:",
            options=list(step_opts.keys()),
            format_func=lambda i: step_opts[i],
            key=f"step_{tab_key}_{period}",
        )

    # ── Toggle hiển thị lớp bản đồ ──────────────────────────────────────
    with st.expander("🗂️ Tuỳ chọn hiển thị lớp bản đồ", expanded=False):
        tc1, tc2, tc3, tc4 = st.columns(4)
        show_tinh     = tc1.checkbox("🏛️ Ranh giới tỉnh", value=True,  key=f"tinh_{tab_key}_{period}")
        show_xa       = tc2.checkbox("🏘️ Ranh giới xã",   value=False, key=f"xa_{tab_key}_{period}")
        show_ten_xa   = tc3.checkbox("🏷️ Tên xã",         value=False, key=f"tenxa_{tab_key}_{period}")
        show_ten_tinh = tc4.checkbox("📍 Tên tỉnh",        value=False, key=f"tentinh_{tab_key}_{period}")

    # ── Chuẩn bị dữ liệu ────────────────────────────────────────────────
    data2d = data3d[selected_step]
    meta   = avail[selected_var]
    t_lbl  = f"Tháng {tlabels[selected_step]}"

    # Chuyển dữ liệu NC (2-D hoặc 1-D) sang điểm phẳng
    if lon1d.ndim == 1 and lat1d.ndim == 1:
        lon2d, lat2d = np.meshgrid(lon1d, lat1d)
    else:
        lon2d, lat2d = lon1d, lat1d

    # Cắt bbox Quảng Ninh để giảm số điểm đưa vào IDW
    mask_bbox = (
        (lon2d >= QN_MINX) & (lon2d <= QN_MAXX) &
        (lat2d >= QN_MINY) & (lat2d <= QN_MAXY)
    )
    lon_pts  = lon2d[mask_bbox].ravel()
    lat_pts  = lat2d[mask_bbox].ravel()
    data_pts = data2d[mask_bbox].ravel()

    # ── Thống kê nhanh (trên vùng QN) ──────────────────────────────────
    valid_pts = data_pts[~np.isnan(data_pts)]
    if valid_pts.size > 0:
        mc = st.columns(4)
        mc[0].metric("Min",        f"{np.nanmin(valid_pts):.2f} {meta['unit']}")
        mc[1].metric("Max",        f"{np.nanmax(valid_pts):.2f} {meta['unit']}")
        mc[2].metric("Trung bình", f"{np.nanmean(valid_pts):.2f} {meta['unit']}")
        mc[3].metric("Std",        f"{np.nanstd(valid_pts):.2f} {meta['unit']}")

    # ── Nội suy + Mask ───────────────────────────────────────────────────
    with st.spinner("Đang nội suy & vẽ bản đồ…"):
        gx, gy, gv = _interpolate_to_qn(data_pts, lon_pts, lat_pts)

        # Mask theo shapefile xã (polygon Quảng Ninh)
        if gdf_xa is not None:
            gv_masked = _apply_shapefile_mask(gx, gy, gv, gdf_xa)
        else:
            gv_masked = gv

        fig = _draw_map(
            gx, gy, gv_masked, gdf_xa, meta,
            group_title, t_lbl,
            show_tinh=show_tinh,
            show_xa=show_xa,
            show_ten_xa=show_ten_xa,
            show_ten_tinh=show_ten_tinh,
        )
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    # ── Tải xuống PNG ────────────────────────────────────────────────────
    buf = BytesIO()
    fig2 = _draw_map(
        gx, gy, gv_masked, gdf_xa, meta,
        group_title, t_lbl,
        show_tinh=show_tinh,
        show_xa=show_xa,
        show_ten_xa=show_ten_xa,
        show_ten_tinh=show_ten_tinh,
    )
    fig2.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig2)
    buf.seek(0)
    st.download_button(
        "⬇️ Tải bản đồ (PNG)",
        data=buf,
        file_name=f"{selected_var}_{period}_{tlabels[selected_step]}.png",
        mime="image/png",
        key=f"dl_{tab_key}_{selected_var}_{selected_step}_{period}",
    )


# ==============================================================================
# HÀM RENDER CHÍNH – app.py gọi đây
# ==============================================================================
def render() -> None:
    st.markdown(
        '<div class="module-header">🔄 Dự báo khí hậu mùa</div>',
        unsafe_allow_html=True,
    )

    # Shapefile xã (tải 1 lần, cache resource)
    gdf_xa = _load_shp_xa()
    if gdf_xa is None:
        st.warning("⚠️ Chưa tải được shapefile xã – bản đồ sẽ không có ranh giới và mask vùng.")

    # Kỳ có dữ liệu (quét thư mục, cache 5 phút)
    periods = _get_periods()
    if not periods:
        st.info(
            f"ℹ️ Chưa tìm thấy thư mục dữ liệu tại `{DATA_DIR}`.\n"
            "Module tự cập nhật khi có dữ liệu mới."
        )
        return

    # Chọn kỳ phát hành
    col_p, _ = st.columns([2, 3])
    with col_p:
        period = st.selectbox(
            "📆 Kỳ phát hành bản tin:",
            options=periods,
            format_func=_period_label,
            key="dubao_period",
        )

    st.markdown("---")

    # 2 tab con
    tab1, tab2 = st.tabs([
        "🌡️  Chuẩn sai Khí hậu",
        "⚠️  Chuẩn sai Cực đoan",
    ])

    with tab1:
        st.markdown(
            '<div class="sub-module">'
            "Chuẩn sai dự báo các yếu tố khí hậu cơ bản (nhiệt độ, lượng mưa, độ ẩm) "
            "so với trung bình nhiều năm – hạn từ 1 đến 3 tháng."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        _render_group(VARS_CLIMATE, period, gdf_xa, "Chuẩn sai Khí hậu", "kh")

    with tab2:
        st.markdown(
            '<div class="sub-module">'
            "Chuẩn sai dự báo các chỉ số cực đoan (nắng nóng, rét đậm, mưa lớn, bốc thoát hơi …) "
            "– hạn từ 1 đến 3 tháng."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        _render_group(VARS_EXTREME, period, gdf_xa, "Chuẩn sai Cực đoan", "cd")
