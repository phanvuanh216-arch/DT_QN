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
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep
import geopandas as gpd
import requests
import xarray as xr
import io, os, re, tempfile, warnings, base64
from datetime import datetime
import branca.colormap as cm
import folium
from streamlit_folium import st_folium

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
    Lọc vùng Quảng Ninh (mã tỉnh 22) cho shapefile tỉnh.
    Trả về (gdf_tinh_qn, gdf_xa) hoặc (None, None) nếu lỗi.
    """
    exts = [".shp", ".dbf", ".shx", ".prj"]
    tmp_dir = tempfile.mkdtemp()

    def _download_shp(name):
        """Tải một bộ shapefile về tmp_dir, trả về đường dẫn .shp hoặc None."""
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

    gdf_tinh_qn = None
    gdf_xa      = None

    try:
        # ── Ranh giới tỉnh → lọc Quảng Ninh ──
        path_tinh = _download_shp("RG_34TINH")
        if path_tinh:
            gdf_tinh = gpd.read_file(path_tinh)
            if gdf_tinh.crs and gdf_tinh.crs.to_epsg() != 4326:
                gdf_tinh = gdf_tinh.to_crs(epsg=4326)
            # Lọc Quảng Ninh: thử các cột tên tỉnh / mã tỉnh phổ biến
            cols = [c.upper() for c in gdf_tinh.columns]
            qn_mask = None
            for col_raw in gdf_tinh.columns:
                col_up = col_raw.upper()
                if col_up in ("TINH", "TEN_TINH", "PROVINCE", "NAME"):
                    qn_mask = gdf_tinh[col_raw].str.contains("Quảng Ninh|Quang Ninh", case=False, na=False)
                    break
                elif col_up in ("MATINH", "MA_TINH", "TINH_CD", "PROVCODE", "MA"):
                    # Mã tỉnh Quảng Ninh = 22
                    try:
                        qn_mask = gdf_tinh[col_raw].astype(str).str.strip() == "22"
                    except:
                        pass
                    break
            if qn_mask is not None and qn_mask.any():
                gdf_tinh_qn = gdf_tinh[qn_mask].copy()
            else:
                # Nếu không lọc được thì bỏ qua lớp tỉnh
                gdf_tinh_qn = None
    except Exception:
        gdf_tinh_qn = None

    try:
        # ── Ranh giới xã vùng nghiên cứu ──
        path_xa = _download_shp("QN_XA_FINAL")
        if path_xa:
            gdf_xa = gpd.read_file(path_xa)
            if gdf_xa.crs and gdf_xa.crs.to_epsg() != 4326:
                gdf_xa = gdf_xa.to_crs(epsg=4326)
    except Exception:
        gdf_xa = None

    return gdf_tinh_qn, gdf_xa


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
                         gdf_tinh_qn, gdf_xa):
    """
    Nội suy IDW → (folium.Map, matplotlib.Figure, err_str).
    Các lớp ranh giới luôn được thêm vào bản đồ Folium;
    người dùng bật/tắt trực tiếp qua LayerControl trong bản đồ.
    """
    # Xác định bbox từ shapefile xã (ưu tiên) hoặc tỉnh hoặc fallback
    ref_gdf = gdf_xa if (gdf_xa is not None and not gdf_xa.empty) else gdf_tinh_qn
    if ref_gdf is not None and not ref_gdf.empty:
        minx, miny, maxx, maxy = ref_gdf.total_bounds
        minx -= 0.2; miny -= 0.2; maxx += 0.2; maxy += 0.2
        shape_union = ref_gdf.unary_union
    else:
        minx, miny, maxx, maxy = 106.3, 20.6, 108.3, 21.8
        shape_union = None

    # Lọc điểm trong vùng mở rộng
    buf = 1.5
    ok = (lons >= minx-buf) & (lons <= maxx+buf) & (lats >= miny-buf) & (lats <= maxy+buf)
    xi, yi, zi = lons[ok], lats[ok], vals[ok]
    if xi.size == 0:
        return None, None, "Không có điểm dữ liệu trong vùng Quảng Ninh"

    # Lưới nội suy
    GRID_N, SIGMA = 400, 1.0
    gx, gy = np.meshgrid(np.linspace(minx, maxx, GRID_N), np.linspace(miny, maxy, GRID_N))
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
    gv = idw_knn(xi, yi, zi, grid_xy).reshape(gx.shape)
    if SIGMA > 0:
        gv = gaussian_filter(gv, sigma=SIGMA)

    # Mask ranh giới theo vùng nghiên cứu
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

    # ── Folium ──
    rgba = cmap(norm(gv))
    rgba[np.isnan(gv)] = [0, 0, 0, 0]
    buf_png = io.BytesIO()
    plt.imsave(buf_png, np.flipud(rgba), format="png")
    buf_png.seek(0)
    img_b64 = base64.b64encode(buf_png.read()).decode()

    m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], tiles=None, zoom_start=8)
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    folium.TileLayer("CartoDB positron", name="🗺️ Nền sáng",     overlay=False, control=True, show=True).add_to(m)
    folium.TileLayer("OpenStreetMap",    name="🗺️ OpenStreetMap", overlay=False, control=True, show=False).add_to(m)
    folium.raster_layers.ImageOverlay(
        image=f"data:image/png;base64,{img_b64}",
        bounds=[[miny, minx], [maxy, maxx]],
        opacity=0.80, name="🎨 Lớp nội suy", interactive=False
    ).add_to(m)

    # Tìm cột tên xã (dùng cho cả Folium lẫn matplotlib)
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

    # Lớp ranh giới tỉnh Quảng Ninh (mặc định bật, tắt được qua LayerControl)
    if gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        folium.GeoJson(
            gdf_tinh_qn,
            name="🏛️ Ranh giới tỉnh",
            show=True,
            style_function=lambda x: {
                "fillColor": "transparent", "color": "#1a1a1a", "weight": 2.0
            }
        ).add_to(m)

    # Lớp ranh giới xã (mặc định bật, tắt được qua LayerControl)
    if gdf_xa is not None and not gdf_xa.empty:
        folium.GeoJson(
            gdf_xa,
            name="🏘️ Ranh giới xã",
            show=True,
            style_function=lambda x: {
                "fillColor": "transparent", "color": "#444444", "weight": 1.0, "dashArray": "4 2"
            }
        ).add_to(m)

    # Lớp nhãn tên xã — đặt trong FeatureGroup để bật/tắt được qua LayerControl
    # Mặc định tắt; người dùng bật khi cần
    if gdf_xa is not None and not gdf_xa.empty and xa_name_col:
        label_group = folium.FeatureGroup(name="🔤 Tên xã", show=False)
        for _, row in gdf_xa.iterrows():
            try:
                centroid = row.geometry.centroid
                folium.Marker(
                    location=[centroid.y, centroid.x],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size:8px;color:#111;font-weight:600;'
                             f'white-space:nowrap;text-shadow:1px 1px 2px #fff,-1px -1px 2px #fff">'
                             f'{row[xa_name_col]}</div>',
                        icon_size=(120, 20), icon_anchor=(60, 10)
                    )
                ).add_to(label_group)
            except Exception:
                pass
        label_group.add_to(m)

    cm.StepColormap(
        colors=[mcolors.to_hex(cmap(norm(v))) for v in levels[:-1]],
        vmin=levels[0], vmax=levels[-1], index=levels,
        caption=f"{title} ({unit})"
    ).add_to(m)
    folium.LayerControl(position="topleft", collapsed=False).add_to(m)

    # ── Matplotlib static ──
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    im = ax.imshow(gv, extent=[minx, maxx, miny, maxy],
                   cmap=cmap, norm=norm, interpolation="bilinear", origin="lower")
    if gdf_tinh_qn is not None and not gdf_tinh_qn.empty:
        gdf_tinh_qn.boundary.plot(ax=ax, edgecolor="#1a1a1a", linewidth=1.5)
    if gdf_xa is not None and not gdf_xa.empty:
        gdf_xa.boundary.plot(ax=ax, edgecolor="#555555", linewidth=0.7, linestyle="--")
    if gdf_xa is not None and not gdf_xa.empty and xa_name_col:
        for _, row in gdf_xa.iterrows():
            try:
                c = row.geometry.centroid
                ax.text(c.x, c.y, str(row[xa_name_col]),
                        fontsize=5, ha="center", va="center", color="#111",
                        fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", alpha=0.5, ec="none"))
            except Exception:
                pass
    cbar = plt.colorbar(im, ax=ax, extend="both", shrink=0.75, pad=0.02)
    cbar.set_label(f"Chuẩn sai ({unit})", fontsize=10)
    cbar.set_ticks(levels); cbar.set_ticklabels([str(v) for v in levels])
    ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy)
    ax.set_xlabel("Kinh độ"); ax.set_ylabel("Vĩ độ")
    ax.ticklabel_format(useOffset=False, style="plain")
    plt.tight_layout()
    return m, fig, None


def render_var_panel(var_prefix, meta, period, month_idx, gdf_tinh_qn, gdf_xa,
                     month_labels, state_key: str):
    """
    Tải → nội suy → lưu kết quả vào st.session_state[state_key].
    Hàm display_panel() sẽ đọc và hiển thị — kết quả không biến mất khi re-run.
    """
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
        fmap, fig, err2 = interpolate_and_plot(
            lons, lats, vals, meta, title, gdf_tinh_qn, gdf_xa
        )
    if err2:
        st.session_state[state_key] = {"error": err2}
        return

    # Lưu PNG vào bytes để download
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    png_bytes = buf.getvalue()
    plt.close(fig)

    # Lưu toàn bộ kết quả vào session_state — tồn tại qua các lần re-run
    st.session_state[state_key] = {
        "fmap":      fmap,
        "png_bytes": png_bytes,
        "title":     title,
        "label":     meta["label"],
        "filename":  f"chuan_sai_{var_prefix.replace('.','_')}_{period}_t{month_idx+1}.png",
        "error":     None,
    }


def display_panel(state_key: str):
    """Hiển thị bản đồ và nút download từ session_state — luôn hiện dù có re-run."""
    result = st.session_state.get(state_key)
    if result is None:
        return
    if result.get("error"):
        st.error(f"❌ {result['error']}")
        return
    st_folium(result["fmap"], width=None, height=520, use_container_width=True)
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
        gdf_tinh_qn, gdf_xa = load_shapefiles()

    if gdf_tinh_qn is None and gdf_xa is None:
        st.warning("⚠️ Không tải được shapefile – bản đồ sẽ không có ranh giới.")

    with st.spinner("🔍 Kiểm tra dữ liệu mới nhất trên server …"):
        periods = fetch_available_periods()
    if not periods:
        st.error("❌ Không kết nối được server hoặc chưa có dữ liệu.")
        return

    # ── Bộ điều khiển kỳ / hạn ──
    periods_desc   = list(reversed(periods))
    yr_mo_labels   = [f"{p[:4]}/{p[4:]}" for p in periods_desc]

    col1, col2 = st.columns([2, 2])
    with col1:
        sel_idx = st.selectbox(
            "📅 Kỳ dự báo:", range(len(periods_desc)),
            format_func=lambda i: yr_mo_labels[i],
            help="Tự động cập nhật khi server có thư mục mới"
        )
        sel_period = periods_desc[sel_idx]

    yr, mo = int(sel_period[:4]), int(sel_period[4:])

    # Hạn dự báo: tháng kỳ phát + 1, +2, +3
    # Ví dụ kỳ 202505 → hạn T6/2025, T7/2025, T8/2025
    month_labels = []
    for d in range(1, 4):          # d = 1, 2, 3  (thay vì 0, 1, 2)
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

    # ── 2 tab con ──
    tab_c, tab_e = st.tabs(["🌡️ Chuẩn sai dự báo khí hậu", "⚠️ Chuẩn sai dự báo cực đoan"])

    with tab_c:
        sel_c = st.selectbox("Chọn biến:", list(CLIMATE_VARS.keys()),
                             format_func=lambda k: CLIMATE_VARS[k]["label"],
                             key="sel_c")
        if st.button("🗺️ Vẽ bản đồ", key="btn_c", type="primary"):
            render_var_panel(sel_c, CLIMATE_VARS[sel_c], sel_period, month_idx,
                             gdf_tinh_qn, gdf_xa, month_labels, state_key="map_c")
        display_panel("map_c")

    with tab_e:
        sel_e = st.selectbox("Chọn biến:", list(EXTREME_VARS.keys()),
                             format_func=lambda k: EXTREME_VARS[k]["label"],
                             key="sel_e")
        if st.button("🗺️ Vẽ bản đồ", key="btn_e", type="primary"):
            render_var_panel(sel_e, EXTREME_VARS[sel_e], sel_period, month_idx,
                             gdf_tinh_qn, gdf_xa, month_labels, state_key="map_e")
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
    st.markdown("*Phiên bản 1.0 – 06/2026*")

# ── Router ──
if   menu == "🏠 Tổng quan":                          page_tong_quan()
elif menu == "🔄 Dự báo khí hậu mùa":                page_du_bao()
elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":   page_ban_tin_xa()
elif menu == "💾 Bản tin đã lưu":                     page_ban_tin_da_luu()
elif menu == "📤 Export bản tin":                      page_export()
elif menu == "💬 Phản hồi":                            page_phan_hoi()
