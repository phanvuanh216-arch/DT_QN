# -*- coding: utf-8 -*-
"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
File duy nhất, không cần thư mục modules/
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import Patch
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep
import geopandas as gpd
import requests
import xarray as xr
import io, os, re, tempfile, warnings, base64
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
    .module-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%);
        color: white; padding: 12px 20px; border-radius: 8px;
        font-size: 1.1rem; font-weight: bold; margin-bottom: 10px;
        display: flex; align-items: center; gap: 8px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e8f4f8; border-radius: 6px 6px 0 0;
        padding: 8px 16px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a5f !important; color: white !important;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #2d3748 100%);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HẰNG SỐ
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL    = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
SHP_QN_URL  = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"

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
# HÀM TIỆN ÍCH – DỮ LIỆU
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)
def fetch_available_periods() -> list:
    """Lấy danh sách thư mục YYYYMM từ server (tự cập nhật mỗi 30 phút)."""
    try:
        resp = requests.get(BASE_URL, timeout=10)
        resp.raise_for_status()
        periods = sorted(set(re.findall(r'(\d{6})/', resp.text)))
        return periods
    except Exception as e:
        st.warning(f"⚠️ Không thể lấy danh sách thư mục: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def download_nc(period: str, var_prefix: str):
    """Tải file NetCDF từ server về bytes."""
    url = f"{BASE_URL}{period}/{var_prefix}.{period}.nc"
    try:
        resp = requests.get(url, timeout=60)
        return resp.content if resp.status_code == 200 else None
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_nc_data(nc_bytes: bytes, month_idx: int):
    """Đọc NetCDF từ bytes → (lons, lats, vals, err)."""
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
        f.write(nc_bytes)
        tmp = f.name
    try:
        ds = xr.open_dataset(tmp)
        coord_names = {c.lower() for c in ds.coords}
        data_vars = [v for v in ds.data_vars if v.lower() not in coord_names]
        if not data_vars:
            return None, None, None, "Không tìm thấy biến dữ liệu"
        da = ds[data_vars[0]]

        # Chọn tháng
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
        ds.close()
        os.unlink(tmp)
        return flat_lon[ok], flat_lat[ok], flat_val[ok], None
    except Exception as e:
        try: os.unlink(tmp)
        except: pass
        return None, None, None, str(e)


@st.cache_resource(show_spinner=False)
def load_shapefiles():
    """
    Tải shapefile tỉnh (RG_34TINH) và xã vùng nghiên cứu (QN_XA_FINAL) từ GitHub.
    Trả về (gdf_all_tinh, gdf_tinh_qn, gdf_xa):
      - gdf_all_tinh : toàn bộ các tỉnh (dùng làm nền)
      - gdf_tinh_qn  : chỉ Quảng Ninh (dùng vẽ viền đậm)
      - gdf_xa       : ranh giới xã trong vùng nghiên cứu
    """
    exts = [".shp", ".dbf", ".shx", ".prj"]
    tmp_dir = tempfile.mkdtemp()

    def _download_shp(name):
        ok = True
        for ext in exts:
            r = requests.get(SHP_QN_URL + name + ext, timeout=30)
            if r.status_code == 200:
                with open(os.path.join(tmp_dir, name + ext), "wb") as f:
                    f.write(r.content)
            else:
                ok = False
        shp_path = os.path.join(tmp_dir, name + ".shp")
        return shp_path if ok and os.path.exists(shp_path) else None

    gdf_all_tinh = None
    gdf_tinh_qn  = None
    gdf_xa       = None

    try:
        path_tinh = _download_shp("RG_34TINH")
        if path_tinh:
            gdf_all = gpd.read_file(path_tinh)
            if gdf_all.crs and gdf_all.crs.to_epsg() != 4326:
                gdf_all = gdf_all.to_crs(epsg=4326)
            gdf_all_tinh = gdf_all.copy()

            # Lọc riêng Quảng Ninh
            qn_mask = None
            for col_raw in gdf_all.columns:
                col_up = col_raw.upper()
                if col_up in ("TINH", "TEN_TINH", "PROVINCE", "NAME"):
                    qn_mask = gdf_all[col_raw].str.contains(
                        "Quảng Ninh|Quang Ninh", case=False, na=False)
                    break
                elif col_up in ("MATINH", "MA_TINH", "TINH_CD", "PROVCODE", "MA"):
                    try:
                        qn_mask = gdf_all[col_raw].astype(str).str.strip() == "22"
                    except:
                        pass
                    break
            if qn_mask is not None and qn_mask.any():
                gdf_tinh_qn = gdf_all[qn_mask].copy()
    except Exception:
        gdf_all_tinh = None
        gdf_tinh_qn  = None

    try:
        path_xa = _download_shp("QN_XA_FINAL")
        if path_xa:
            gdf_xa = gpd.read_file(path_xa)
            if gdf_xa.crs and gdf_xa.crs.to_epsg() != 4326:
                gdf_xa = gdf_xa.to_crs(epsg=4326)
    except Exception:
        gdf_xa = None

    return gdf_all_tinh, gdf_tinh_qn, gdf_xa


# ══════════════════════════════════════════════════════════════════════════════
# HÀM NỘI SUY IDW-KNN
# ══════════════════════════════════════════════════════════════════════════════

def idw_knn(xi, yi, zi, query_xy, k=12, power=3.0, eps=1e-12):
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


def interpolate_and_plot(lons, lats, vals, meta: dict, title: str,
                         gdf_all_tinh, gdf_tinh_qn, gdf_xa):
    """
    Nội suy IDW chỉ trong vùng Quảng Ninh.
    Vẽ nền xám các tỉnh lân cận, zoom cố định theo bbox Quảng Ninh.
    Trả về (png_bytes, err_str).
    """
    # ── 1. Xác định bbox zoom theo Quảng Ninh ──
    # Ưu tiên: gdf_xa → gdf_tinh_qn → fallback hardcode
    ref_qn = None
    if gdf_xa is not None and not gdf_xa.empty:
        ref_qn = gdf_xa
    elif gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        ref_qn = gdf_tinh_qn

    if ref_qn is not None:
        minx, miny, maxx, maxy = ref_qn.total_bounds
    else:
        minx, miny, maxx, maxy = 106.3, 20.6, 108.3, 21.8

    # Buffer nhỏ xung quanh để không bị sát viền
    BUF = 0.12
    plot_minx = minx - BUF
    plot_miny = miny - BUF
    plot_maxx = maxx + BUF
    plot_maxy = maxy + BUF

    # ── 2. Xác định polygon mask nội suy (chỉ Quảng Ninh) ──
    if ref_qn is not None:
        shape_union = ref_qn.unary_union
    elif gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        shape_union = gdf_tinh_qn.unary_union
    else:
        shape_union = None

    # ── 3. Lọc điểm dữ liệu – mở rộng hơn để IDW có đủ hàng xóm ──
    buf_data = 1.5
    ok = ((lons >= minx - buf_data) & (lons <= maxx + buf_data) &
          (lats >= miny - buf_data) & (lats <= maxy + buf_data))
    xi, yi, zi = lons[ok], lats[ok], vals[ok]
    if xi.size == 0:
        return None, "Không có điểm dữ liệu trong vùng Quảng Ninh"

    # ── 4. Lưới nội suy (chỉ trong bbox Quảng Ninh) ──
    GRID_N, SIGMA = 500, 1.2
    gx, gy = np.meshgrid(
        np.linspace(minx, maxx, GRID_N),
        np.linspace(miny, maxy, GRID_N)
    )
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
    gv = idw_knn(xi, yi, zi, grid_xy).reshape(gx.shape)
    if SIGMA > 0:
        gv = gaussian_filter(gv, sigma=SIGMA)

    # ── 5. Mask: chỉ giữ pixel nằm trong polygon Quảng Ninh ──
    if shape_union is not None:
        prep_s = prep(shape_union)
        mask_flat = np.fromiter(
            (prep_s.contains(Point(px, py)) for px, py in grid_xy),
            count=grid_xy.shape[0], dtype=bool
        ).reshape(gx.shape)
        gv = np.where(mask_flat, gv, np.nan)

    levels = sorted(meta.get("levels", list(range(-5, 6))))
    cmap   = plt.get_cmap(meta.get("cmap", "RdBu_r"))
    norm   = BoundaryNorm(levels, ncolors=cmap.N, extend="both")
    unit   = meta.get("unit", "")

    # Tên xã
    xa_name_col = None
    if gdf_xa is not None and not gdf_xa.empty:
        for col in gdf_xa.columns:
            if col.upper() in ("TEN_XA", "TENXA", "XA", "NAME", "TEN"):
                xa_name_col = col
                break
        if xa_name_col is None:
            for col in gdf_xa.columns:
                if col.lower() != "geometry":
                    xa_name_col = col
                    break

    # ── 6. Vẽ matplotlib ──
    aspect = (plot_maxy - plot_miny) / (plot_maxx - plot_minx)
    fig_w  = 11
    fig_h  = max(7, fig_w * aspect + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)

    # 6a. Nền xám tất cả các tỉnh (clip theo extent hiển thị)
    if gdf_all_tinh is not None and not gdf_all_tinh.empty:
        gdf_all_tinh.plot(ax=ax, facecolor="#dde3e8", edgecolor="#aab0b8",
                          linewidth=0.6, zorder=1)

    # 6b. Lớp màu nội suy (chỉ Quảng Ninh)
    im = ax.imshow(
        gv,
        extent=[minx, maxx, miny, maxy],   # extent đúng với lưới nội suy
        cmap=cmap, norm=norm,
        interpolation="bilinear",
        origin="lower", alpha=0.92, zorder=2
    )

    # 6c. Viền tỉnh Quảng Ninh đậm hơn
    if gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        gdf_tinh_qn.boundary.plot(ax=ax, edgecolor="#111111",
                                   linewidth=2.0, zorder=4)

    # 6d. Ranh giới xã
    if gdf_xa is not None and not gdf_xa.empty:
        gdf_xa.boundary.plot(ax=ax, edgecolor="#444444",
                              linewidth=0.8, linestyle="--", zorder=3)

    # 6e. Tên xã
    if gdf_xa is not None and not gdf_xa.empty and xa_name_col:
        for _, row in gdf_xa.iterrows():
            try:
                c = row.geometry.centroid
                ax.text(c.x, c.y, str(row[xa_name_col]),
                        fontsize=5.5, ha="center", va="center",
                        color="#111", fontweight="bold", zorder=5,
                        bbox=dict(boxstyle="round,pad=0.15",
                                  fc="white", alpha=0.55, ec="none"))
            except Exception:
                pass

    # 6f. Colorbar
    cbar = plt.colorbar(im, ax=ax, extend="both",
                        shrink=0.80, pad=0.02, aspect=28)
    cbar.set_label(f"Chuẩn sai ({unit})", fontsize=10)
    cbar.set_ticks(levels)
    cbar.set_ticklabels([str(v) for v in levels], fontsize=8)

    # 6g. Giới hạn zoom cố định theo Quảng Ninh + buffer
    ax.set_xlim(plot_minx, plot_maxx)
    ax.set_ylim(plot_miny, plot_maxy)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Kinh độ (°E)", fontsize=9)
    ax.set_ylabel("Vĩ độ (°N)",   fontsize=9)
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.tick_params(labelsize=8)

    # Legend
    legend_handles = []
    if gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        legend_handles.append(
            Patch(facecolor="none", edgecolor="#111111",
                  linewidth=1.5, label="Ranh giới Quảng Ninh")
        )
    if gdf_xa is not None and not gdf_xa.empty:
        legend_handles.append(
            Patch(facecolor="none", edgecolor="#444444",
                  linewidth=0.8, linestyle="--", label="Ranh giới xã")
        )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="lower right",
                  fontsize=7, framealpha=0.8)

    plt.tight_layout()

    buf_out = io.BytesIO()
    fig.savefig(buf_out, format="png", dpi=150, bbox_inches="tight")
    buf_out.seek(0)
    png_bytes = buf_out.getvalue()
    plt.close(fig)

    return png_bytes, None


def render_var_panel(var_prefix, meta, period, month_idx,
                     gdf_all_tinh, gdf_tinh_qn, gdf_xa,
                     month_labels, state_key: str):
    with st.spinner(f"⏳ Đang tải {meta['label']} …"):
        nc_bytes = download_nc(period, var_prefix)
    if nc_bytes is None:
        st.session_state[state_key] = {"error": f"Không tải được file NC: {var_prefix}.{period}.nc"}
        return

    with st.spinner("🔄 Đang nội suy …"):
        lons, lats, vals, err = load_nc_data(nc_bytes, month_idx)
    if err:
        st.session_state[state_key] = {"error": f"Lỗi đọc dữ liệu: {err}"}
        return

    month_str = month_labels[month_idx] if month_idx < len(month_labels) else f"Tháng +{month_idx+1}"
    title = f"Chuẩn sai {meta['label']} – {month_str} (Kỳ {period[:4]}/{period[4:]})"

    with st.spinner("🗺️ Đang vẽ bản đồ …"):
        png_bytes, err2 = interpolate_and_plot(
            lons, lats, vals, meta, title,
            gdf_all_tinh, gdf_tinh_qn, gdf_xa
        )
    if err2:
        st.session_state[state_key] = {"error": err2}
        return

    st.session_state[state_key] = {
        "png_bytes": png_bytes,
        "label":     meta["label"],
        "filename":  f"chuan_sai_{var_prefix.replace('.','_')}_{period}_t{month_idx+1}.png",
        "error":     None,
    }


def display_panel(state_key: str):
    result = st.session_state.get(state_key)
    if result is None:
        return
    if result.get("error"):
        st.error(f"❌ {result['error']}")
        return
    st.image(result["png_bytes"], use_container_width=True)
    st.download_button(
        f"⬇️ Tải PNG – {result['label']}",
        data=result["png_bytes"],
        file_name=result["filename"],
        mime="image/png",
        key=f"dl_{state_key}",
    )


# ══════════════════════════════════════════════════════════════════════════════
# CÁC SECTION NỘI DUNG
# ══════════════════════════════════════════════════════════════════════════════

def page_tong_quan():
    st.title("🌾 Công cụ quản lý rủi ro khí hậu đối với cây trồng và vật nuôi tỉnh Quảng Ninh")
    st.markdown("Hệ thống hỗ trợ tạo **bản tin cảnh báo khí hậu** cho các xã tại Quảng Ninh, "
                "bao gồm đánh giá rủi ro cho **Lúa, Rau, Lợn, Gà** theo từng kỳ tháng.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏘️ Số xã", "30")
    c2.metric("🌱 Đối tượng nông nghiệp", "4")
    c3.metric("📅 Kỳ dự báo", "3 tháng")
    c4.metric("📄 Bản tin đã tạo", "0")


def page_du_bao():
    st.markdown('<div class="module-header">🔄 Dự báo khí hậu mùa</div>', unsafe_allow_html=True)

    with st.spinner("⏳ Đang tải shapefile …"):
        gdf_all_tinh, gdf_tinh_qn, gdf_xa = load_shapefiles()

    if gdf_all_tinh is None and gdf_xa is None:
        st.warning("⚠️ Không tải được shapefile – bản đồ sẽ không có ranh giới.")

    with st.spinner("🔍 Kiểm tra dữ liệu mới nhất trên server …"):
        periods = fetch_available_periods()
    if not periods:
        st.error("❌ Không kết nối được server hoặc chưa có dữ liệu.")
        return

    periods_desc = list(reversed(periods))
    yr_mo_labels = [f"{p[:4]}/{p[4:]}" for p in periods_desc]

    col1, col2 = st.columns([2, 2])
    with col1:
        sel_idx = st.selectbox(
            "📅 Kỳ dự báo:", range(len(periods_desc)),
            format_func=lambda i: yr_mo_labels[i],
            help="Tự động cập nhật khi server có thư mục mới"
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
            help="3 tháng tiếp theo sau kỳ phát bản tin"
        )

    st.markdown("---")

    tab_c, tab_e = st.tabs(["🌡️ Chuẩn sai dự báo khí hậu", "⚠️ Chuẩn sai dự báo cực đoan"])

    with tab_c:
        sel_c = st.selectbox("Chọn biến:", list(CLIMATE_VARS.keys()),
                             format_func=lambda k: CLIMATE_VARS[k]["label"],
                             key="sel_c")
        if st.button("🗺️ Vẽ bản đồ", key="btn_c", type="primary"):
            render_var_panel(sel_c, CLIMATE_VARS[sel_c], sel_period, month_idx,
                             gdf_all_tinh, gdf_tinh_qn, gdf_xa,
                             month_labels, state_key="map_c")
        display_panel("map_c")

    with tab_e:
        sel_e = st.selectbox("Chọn biến:", list(EXTREME_VARS.keys()),
                             format_func=lambda k: EXTREME_VARS[k]["label"],
                             key="sel_e")
        if st.button("🗺️ Vẽ bản đồ", key="btn_e", type="primary"):
            render_var_panel(sel_e, EXTREME_VARS[sel_e], sel_period, month_idx,
                             gdf_all_tinh, gdf_tinh_qn, gdf_xa,
                             month_labels, state_key="map_e")
        display_panel("map_e")


def page_ban_tin_xa():
    st.markdown('<div class="module-header">📋 Bản tin cảnh báo rủi ro khí hậu</div>', unsafe_allow_html=True)
    st.info("Module đang phát triển.")


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
    st.markdown("*Phiên bản 1.0.3 – 06/2026*")

# ── Router ──
if   menu == "🏠 Tổng quan":                          page_tong_quan()
elif menu == "🔄 Dự báo khí hậu mùa":                page_du_bao()
elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":   page_ban_tin_xa()
elif menu == "💾 Bản tin đã lưu":                     page_ban_tin_da_luu()
elif menu == "📤 Export bản tin":                      page_export()
elif menu == "💬 Phản hồi":                            page_phan_hoi()
