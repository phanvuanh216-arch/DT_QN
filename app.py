"""
modules/du_bao_tu_dong.py
Module: Dự báo khí hậu mùa – được gọi từ app.py qua du_bao_tu_dong.render()

Gồm 2 sub-module (st.tabs):
  1. Chuẩn sai dự báo khí hậu  – T2m, Tx, Tm, R, RH2m
  2. Chuẩn sai dự báo cực đoan – CDD, CWD, Evap, FD13, FD15,
                                  Rx1day, Rx5day, SU35, SU37, SU39
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

import netCDF4 as nc
import geopandas as gpd

# ─── Cấu hình đường dẫn ───────────────────────────────────────────────────────
DATA_DIR = "/imhen-data/share-imhen/phonglv/Detai_QuangNinh/domain_d02"

# Shapefile xã Quảng Ninh trên GitHub (raw download)
_SHP_RAW = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/shp/"
_SHP_EXTS = [".shp", ".dbf", ".shx", ".prj", ".cpg"]
_SHP_NAME = "Quang_Ninh_Xa"

# ─── Danh sách biến ───────────────────────────────────────────────────────────
VARS_CLIMATE: dict[str, dict] = {
    "ano.T2m":  {"label": "Nhiệt độ TB (T₂ₘ)",        "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.Tx":   {"label": "Nhiệt độ tối cao (Tₓ)",     "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.Tm":   {"label": "Nhiệt độ tối thấp (Tₘ)",    "unit": "°C",  "cmap": "RdBu_r",  "vmin": -2.5, "vmax": 2.5},
    "ano.R":    {"label": "Lượng mưa (R)",              "unit": "mm",  "cmap": "BrBG",    "vmin": -150, "vmax": 150},
    "ano.RH2m": {"label": "Độ ẩm tương đối (RH₂ₘ)",   "unit": "%",   "cmap": "BrBG",    "vmin": -10,  "vmax": 10},
}

VARS_EXTREME: dict[str, dict] = {
    "ano.CDD":    {"label": "Ngày khô liên tiếp (CDD)",          "unit": "ngày", "cmap": "YlOrRd", "vmin": -10,  "vmax": 10},
    "ano.CWD":    {"label": "Ngày mưa liên tiếp (CWD)",          "unit": "ngày", "cmap": "YlGnBu", "vmin": -5,   "vmax": 5},
    "ano.Evap":   {"label": "Bốc thoát hơi (Evap)",              "unit": "mm",   "cmap": "BrBG",   "vmin": -50,  "vmax": 50},
    "ano.FD13":   {"label": "Ngày rét đậm ≤13 °C (FD13)",        "unit": "ngày", "cmap": "Blues",  "vmin": -5,   "vmax": 5},
    "ano.FD15":   {"label": "Ngày rét hại ≤15 °C (FD15)",        "unit": "ngày", "cmap": "PuBu",   "vmin": -5,   "vmax": 5},
    "ano.Rx1day": {"label": "Mưa 1 ngày lớn nhất (Rx1day)",      "unit": "mm",   "cmap": "BuPu",   "vmin": -50,  "vmax": 50},
    "ano.Rx5day": {"label": "Mưa 5 ngày lớn nhất (Rx5day)",      "unit": "mm",   "cmap": "BuPu",   "vmin": -100, "vmax": 100},
    "ano.SU35":   {"label": "Ngày nắng nóng ≥35 °C (SU35)",      "unit": "ngày", "cmap": "YlOrRd", "vmin": -10,  "vmax": 10},
    "ano.SU37":   {"label": "Ngày nắng nóng g.gắt ≥37 °C (SU37)","unit": "ngày", "cmap": "OrRd",   "vmin": -5,   "vmax": 5},
    "ano.SU39":   {"label": "Ngày nắng nóng đb ≥39 °C (SU39)",   "unit": "ngày", "cmap": "Reds",   "vmin": -3,   "vmax": 3},
}


# ─── Shapefile ────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Đang tải shapefile Quảng Ninh…")
def _load_shapefile() -> gpd.GeoDataFrame | None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for ext in _SHP_EXTS:
                fname = _SHP_NAME + ext
                r = requests.get(_SHP_RAW + fname, timeout=20)
                if r.status_code == 200:
                    with open(os.path.join(tmp, fname), "wb") as f:
                        f.write(r.content)
            shp = os.path.join(tmp, _SHP_NAME + ".shp")
            if os.path.exists(shp):
                return gpd.read_file(shp)
    except Exception as e:
        st.warning(f"⚠️ Không tải được shapefile: {e}")
    return None


# ─── Quét danh sách kỳ (YYYYMM) ──────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _get_periods() -> list[str]:
    """Trả về danh sách YYYYMM giảm dần từ DATA_DIR."""
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


# ─── Đọc NetCDF ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Đang đọc dữ liệu…")
def _read_nc(path: str, var_key: str):
    """
    Trả về (data3d, lon2d, lat2d, time_labels).
    data3d shape: (≤3, ny, nx).  time_labels: list[str].
    """
    try:
        ds = nc.Dataset(path)
        short = var_key.split(".")[-1]          # ví dụ "T2m", "R", …

        # Tìm biến dữ liệu
        if short in ds.variables:
            raw = ds.variables[short][:]
        else:
            skip = {"lon", "lat", "time", "longitude", "latitude"}
            cands = [v for v in ds.variables if v not in skip]
            if not cands:
                ds.close(); return None, None, None, None
            raw = ds.variables[cands[0]][:]

        # Tọa độ
        lon_k = "lon" if "lon" in ds.variables else "longitude"
        lat_k = "lat" if "lat" in ds.variables else "latitude"
        lon = ds.variables[lon_k][:]
        lat = ds.variables[lat_k][:]
        if lon.ndim == 1 and lat.ndim == 1:
            lon2d, lat2d = np.meshgrid(lon, lat)
        else:
            lon2d, lat2d = np.array(lon), np.array(lat)

        # Thời gian
        tv = ds.variables.get("time")
        if tv is not None:
            try:
                cal = getattr(tv, "calendar", "gregorian")
                tms = nc.num2date(tv[:], tv.units, calendar=cal)
                tlabels = [f"{t.year}-{t.month:02d}" for t in tms]
            except Exception:
                tlabels = [f"Bước {i+1}" for i in range(raw.shape[0])]
        else:
            tlabels = [f"Bước {i+1}" for i in range(raw.shape[0])]

        ds.close()

        # Giới hạn 3 hạn đầu
        data = np.ma.filled(np.array(raw), np.nan)[:3]
        tlabels = tlabels[:3]
        return data, lon2d, lat2d, tlabels

    except Exception as e:
        st.error(f"Lỗi đọc NetCDF: {e}")
        return None, None, None, None


# ─── Vẽ bản đồ ────────────────────────────────────────────────────────────────
def _draw_map(data2d, lon2d, lat2d, gdf, meta: dict,
              group_title: str, time_label: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 5.8), dpi=130)
    fig.patch.set_facecolor("#f0f4f8")
    ax.set_facecolor("#dce8f0")

    vmin, vmax = meta["vmin"], meta["vmax"]
    cmap = plt.get_cmap(meta["cmap"])
    norm = (mcolors.TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
            if vmin < 0 < vmax else mcolors.Normalize(vmin=vmin, vmax=vmax))

    pcm = ax.pcolormesh(lon2d, lat2d, data2d,
                        cmap=cmap, norm=norm, shading="auto",
                        alpha=0.92, zorder=1)

    # Đường đẳng trị nhẹ
    try:
        lvs = np.linspace(vmin, vmax, 11)
        ax.contour(lon2d, lat2d, data2d,
                   levels=lvs, colors="white",
                   linewidths=0.35, alpha=0.5, zorder=2)
    except Exception:
        pass

    # Shapefile
    if gdf is not None:
        try:
            g = gdf.to_crs("EPSG:4326") if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf
            g.boundary.plot(ax=ax, edgecolor="#2c3e50",
                            linewidth=0.55, zorder=3)
        except Exception:
            pass

    cb = fig.colorbar(pcm, ax=ax, orientation="vertical",
                      fraction=0.028, pad=0.02, shrink=0.82)
    cb.set_label(f"Chuẩn sai ({meta['unit']})", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)

    ax.set_title(f"{group_title}\n{meta['label']}  –  {time_label}",
                 fontsize=9, fontweight="bold", pad=8, color="#1e3a5f")
    ax.set_xlabel("Kinh độ (°E)", fontsize=7)
    ax.set_ylabel("Vĩ độ (°N)", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_xlim(106.3, 108.4)
    ax.set_ylim(20.6, 22.0)
    ax.grid(linestyle="--", linewidth=0.3, color="gray", alpha=0.4, zorder=0)
    plt.tight_layout()
    return fig


# ─── Panel chung cho mỗi nhóm biến ───────────────────────────────────────────
def _render_group(var_dict: dict, period: str,
                  gdf, group_title: str) -> None:
    period_dir = os.path.join(DATA_DIR, period)

    # Lọc biến có file thực
    avail = {
        vk: vm for vk, vm in var_dict.items()
        if os.path.isfile(os.path.join(period_dir, f"{vk}.{period}.nc"))
    }

    if not avail:
        st.warning(
            f"⚠️ Chưa tìm thấy file dữ liệu trong thư mục:\n`{period_dir}`\n\n"
            "File cần có dạng: `ano.T2m.YYYYMM.nc`, `ano.R.YYYYMM.nc` …"
        )
        return

    col_var, col_step = st.columns([2, 1])

    with col_var:
        selected_var = st.selectbox(
            "🌡️ Chọn biến:",
            options=list(avail.keys()),
            format_func=lambda k: avail[k]["label"],
            key=f"var_{group_title}_{period}",
        )

    nc_path = os.path.join(period_dir, f"{selected_var}.{period}.nc")
    data3d, lon2d, lat2d, tlabels = _read_nc(nc_path, selected_var)

    if data3d is None:
        st.error("❌ Không đọc được dữ liệu.")
        return

    with col_step:
        step_opts = {i: f"Tháng {tlabels[i]}" for i in range(len(tlabels))}
        selected_step = st.selectbox(
            "📅 Hạn dự báo:",
            options=list(step_opts.keys()),
            format_func=lambda i: step_opts[i],
            key=f"step_{group_title}_{period}",
        )

    data2d = data3d[selected_step]
    meta   = avail[selected_var]
    t_lbl  = f"Tháng {tlabels[selected_step]}"

    # Thống kê nhanh
    valid = data2d[~np.isnan(data2d)]
    if valid.size > 0:
        mc = st.columns(4)
        mc[0].metric("Min",        f"{np.nanmin(valid):.2f} {meta['unit']}")
        mc[1].metric("Max",        f"{np.nanmax(valid):.2f} {meta['unit']}")
        mc[2].metric("Trung bình", f"{np.nanmean(valid):.2f} {meta['unit']}")
        mc[3].metric("Std",        f"{np.nanstd(valid):.2f} {meta['unit']}")

    # Bản đồ
    with st.spinner("Đang vẽ bản đồ…"):
        fig = _draw_map(data2d, lon2d, lat2d, gdf, meta, group_title, t_lbl)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    # Tải xuống PNG
    buf = BytesIO()
    fig2 = _draw_map(data2d, lon2d, lat2d, gdf, meta, group_title, t_lbl)
    fig2.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig2)
    buf.seek(0)
    st.download_button(
        "⬇️ Tải bản đồ (PNG)",
        data=buf,
        file_name=f"{selected_var}_{period}_{tlabels[selected_step]}.png",
        mime="image/png",
        key=f"dl_{group_title}_{selected_var}_{selected_step}",
    )


# ─── Hàm render chính – app.py gọi đây ───────────────────────────────────────
def render() -> None:
    st.markdown("""
    <div class="module-header">🔄 Dự báo khí hậu mùa</div>
    """, unsafe_allow_html=True)

    # Shapefile (cache resource, tải 1 lần)
    gdf = _load_shapefile()

    # Kỳ có dữ liệu
    periods = _get_periods()
    if not periods:
        st.info(
            f"ℹ️ Chưa tìm thấy thư mục dữ liệu tại `{DATA_DIR}`.\n"
            "Module sẽ tự cập nhật khi có dữ liệu mới."
        )
        return

    # Widget chọn kỳ
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
            'Chuẩn sai dự báo các yếu tố khí hậu cơ bản (nhiệt độ, lượng mưa, độ ẩm) '
            'so với trung bình nhiều năm – hạn từ 1 đến 3 tháng.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        _render_group(VARS_CLIMATE, period, gdf, "Chuẩn sai Khí hậu")

    with tab2:
        st.markdown(
            '<div class="sub-module">'
            'Chuẩn sai dự báo các chỉ số cực đoan (nắng nóng, rét đậm, mưa lớn, bốc thoát hơi …) '
            '– hạn từ 1 đến 3 tháng.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        _render_group(VARS_EXTREME, period, gdf, "Chuẩn sai Cực đoan")
