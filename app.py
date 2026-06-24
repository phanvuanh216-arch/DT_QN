"""
modules/du_bao_tu_dong.py
Module DỰ BÁO TỰ ĐỘNG – tải và hiển thị dữ liệu dự báo từ server
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from utils.data_fetcher import XA_LIST, KY_THANG, load_data_for_xa, DOI_TUONG
from utils.nc_data_fetcher import (
    NHOM_KHI_HAU,
    NHOM_CUC_DOAN,
    lay_danh_sach_ky_chay,
    sinh_nhan_han_du_bao,
    dinh_dang_ky_chay,
    doc_du_lieu_raster,
    mask_raster_theo_tinh,
    doc_shapefile_xa,
    doc_ranh_gioi_tinh,
    noi_suy_idw_luoi_min,
)


def render():
    """Điểm vào chính của module – giữ nguyên module con cũ (mock theo xã)
    và bổ sung thêm module con mới đọc dữ liệu NetCDF thật từ server, dưới dạng 2 tab."""
    tab_xa, tab_netcdf = st.tabs(
        ["🏘️ Dự báo theo xã (mô phỏng)", "🌍 Dự báo khí hậu mùa (dữ liệu NetCDF)"]
    )

    with tab_xa:
        _render_du_bao_theo_xa()

    with tab_netcdf:
        _render_du_bao_netcdf()


def _render_du_bao_theo_xa():
    """Module con CŨ – giữ nguyên 100% logic ban đầu (dữ liệu mô phỏng theo xã)."""
    st.markdown('<div class="module-header">🔄 MODULE: Dự báo tự động</div>', unsafe_allow_html=True)
    st.markdown("""
    Module này tự động tải dữ liệu dự báo từ máy chủ
    `http://222.254.32.10/forecast/Detai_QuangNinh/` cho từng xã được chọn.
    """)

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        xa_chon = st.selectbox("🏘️ Chọn xã:", XA_LIST, key="db_xa")
    with col2:
        doi_tuong_chon = st.multiselect(
            "🌱 Đối tượng nông nghiệp:",
            ["Lúa", "Rau", "Lợn", "Gà"],
            default=["Lúa", "Rau", "Lợn", "Gà"],
            key="db_doi_tuong",
        )
    with col3:
        tai_lai = st.button("🔄 Tải dữ liệu", use_container_width=True)

    st.markdown("---")

    # Tải dữ liệu
    with st.spinner(f"Đang tải dữ liệu cho {xa_chon}..."):
        data, source = load_data_for_xa(xa_chon)

    st.info(f"**Nguồn:** {source}  |  **Xã:** {xa_chon}  |  **Kỳ dự báo:** Tháng 6 – 8/2026")

    # ── Dự báo tháng ─────────────────────────────────────────────────────────
    with st.expander("📊 Dự báo xác suất nhiệt độ & lượng mưa", expanded=True):
        du_bao = data.get("du_bao_thang", {})
        if du_bao:
            rows_nhiet = []
            rows_mua = []
            for ky in KY_THANG:
                if ky in du_bao:
                    nt = du_bao[ky].get("nhiet_do", {})
                    lm = du_bao[ky].get("luong_mua", {})
                    rows_nhiet.append({
                        "Kỳ": ky,
                        "Thấp hơn (%)": nt.get("thap_hon", ""),
                        "Xấp xỉ (%)": nt.get("xap_xi", ""),
                        "Cao hơn (%)": nt.get("cao_hon", ""),
                    })
                    rows_mua.append({
                        "Kỳ": ky,
                        "Thấp hơn (%)": lm.get("thap_hon", ""),
                        "Xấp xỉ (%)": lm.get("xap_xi", ""),
                        "Cao hơn (%)": lm.get("cao_hon", ""),
                    })

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🌡️ Nhiệt độ trung bình nhiều năm**")
                df_nt = pd.DataFrame(rows_nhiet).set_index("Kỳ")
                st.dataframe(df_nt, use_container_width=True)
            with c2:
                st.markdown("**🌧️ Lượng mưa trung bình nhiều năm**")
                df_lm = pd.DataFrame(rows_mua).set_index("Kỳ")
                st.dataframe(df_lm, use_container_width=True)

    # ── Bảng rủi ro theo đối tượng ────────────────────────────────────────────
    doi_tuong_map = {"Lúa": "lua", "Rau": "rau", "Lợn": "lon", "Gà": "ga"}
    rui_ro_data = data.get("rui_ro", {})

    for dt_name in doi_tuong_chon:
        dt_key = doi_tuong_map[dt_name]
        dt_info = DOI_TUONG[dt_key]
        icon = dt_info["icon"]
        color = dt_info["color"]

        with st.expander(f"{icon} Rủi ro {dt_name}", expanded=False):
            dt_rr = rui_ro_data.get(dt_key, {})
            if not dt_rr:
                st.warning("Chưa có dữ liệu rủi ro.")
                continue

            if dt_key == "rau":
                for loai_key, loai_info in dt_info["loai_rau"].items():
                    st.markdown(f"**{loai_info['name']}**")
                    loai_rr = dt_rr.get(loai_key, {})
                    _render_risk_table(loai_rr, KY_THANG, loai_info.get("chu_ky", {}))
            else:
                chu_ky = dt_info.get("chu_ky", {})
                _render_risk_table(dt_rr, KY_THANG, chu_ky)

    # ── Lưu vào session ───────────────────────────────────────────────────────
    if st.button("💾 Lưu dữ liệu này vào Session", key="db_save"):
        if "forecast_cache" not in st.session_state:
            st.session_state["forecast_cache"] = {}
        st.session_state["forecast_cache"][xa_chon] = data
        st.success(f"✅ Đã lưu dữ liệu dự báo cho **{xa_chon}** vào session.")


def _render_risk_table(rr_dict: dict, ky_list: list, chu_ky: dict):
    """Render bảng rủi ro màu sắc theo cấp."""
    from utils.data_fetcher import RISK_LABELS, RISK_COLORS, RISK_TEXT_COLORS

    if not rr_dict:
        st.caption("Không có dữ liệu.")
        return

    rows = []
    if chu_ky:
        rows.append({"Chỉ tiêu": "Chu kỳ sinh trưởng", **{ky: chu_ky.get(ky, "") for ky in ky_list}})

    for indicator, ky_vals in rr_dict.items():
        rows.append({"Chỉ tiêu": indicator, **{ky: ky_vals.get(ky, 0) for ky in ky_list}})

    df = pd.DataFrame(rows).set_index("Chỉ tiêu")

    def color_cell(val):
        if isinstance(val, int):
            bg = RISK_COLORS.get(val, "#fff")
            fg = RISK_TEXT_COLORS.get(val, "#333")
            label = RISK_LABELS.get(val, "")
            return f"background-color: {bg}; color: {fg}; font-weight: bold;"
        return ""

    styled = df.style.map(color_cell, subset=ky_list)
    st.dataframe(styled, use_container_width=True, height=min(250, 50 + 35 * len(rows)))


# ═══════════════════════════════════════════════════════════════════════════
# MODULE CON MỚI – Dự báo khí hậu mùa đọc trực tiếp dữ liệu NetCDF (.nc)
# từ server http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/
# Gồm 2 nhóm: Chuẩn sai dự báo khí hậu / Chuẩn sai dự báo cực đoan
# ═══════════════════════════════════════════════════════════════════════════
def _render_du_bao_netcdf():
    st.markdown(
        '<div class="module-header">🌍 MODULE: Dự báo khí hậu mùa (NetCDF)</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "Bản đồ chuẩn sai dự báo khí hậu mùa cho tỉnh Quảng Ninh, "
        "đọc trực tiếp dữ liệu mô hình (.nc) từ máy chủ nội bộ."
    )

    danh_sach_ky_chay = lay_danh_sach_ky_chay()

    if not danh_sach_ky_chay:
        st.error(
            "⚠️ Không kết nối được tới máy chủ dữ liệu "
            "(`http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/`) "
            "hoặc chưa có kỳ chạy nào. Vui lòng kiểm tra kết nối mạng nội bộ tới máy chủ "
            "hoặc thử lại sau."
        )
        return

    tab_khi_hau, tab_cuc_doan = st.tabs(
        ["🌡️ Chuẩn sai dự báo khí hậu", "🌪️ Chuẩn sai dự báo cực đoan"]
    )

    with tab_khi_hau:
        _render_module_con_netcdf(
            khoa="khihau",
            nhom_bien=NHOM_KHI_HAU,
            danh_sach_ky_chay=danh_sach_ky_chay,
        )

    with tab_cuc_doan:
        _render_module_con_netcdf(
            khoa="cucdoan",
            nhom_bien=NHOM_CUC_DOAN,
            danh_sach_ky_chay=danh_sach_ky_chay,
        )


def _render_module_con_netcdf(khoa: str, nhom_bien: dict, danh_sach_ky_chay: list[str]):
    """Render 1 module con NetCDF (dùng chung cho cả 2 tab khí hậu / cực đoan)."""

    col1, col2, col3 = st.columns([1.3, 1.3, 2])
    with col1:
        ky_chay = st.selectbox(
            "📅 Kỳ chạy mô hình:",
            danh_sach_ky_chay,
            index=0,  # mới nhất luôn ở đầu danh sách (đã sort giảm dần)
            format_func=dinh_dang_ky_chay,
            key=f"{khoa}_ky_chay",
        )
    with col2:
        nhan_han = sinh_nhan_han_du_bao(ky_chay)
        han_chon = st.selectbox(
            "⏱️ Hạn dự báo:",
            options=[h for h, _ in nhan_han],
            format_func=lambda h: dict(nhan_han)[h],
            key=f"{khoa}_han",
        )
    with col3:
        ma_bien = st.selectbox(
            "📊 Biến hiển thị:",
            options=list(nhom_bien.keys()),
            format_func=lambda k: nhom_bien[k]["ten"],
            key=f"{khoa}_bien",
        )

    st.markdown(
        f"**🕐 Thời gian phân tích (kỳ chạy mô hình):** {dinh_dang_ky_chay(ky_chay)}  \n"
        f"**📈 Thời gian dự báo:** {dict(nhan_han)[han_chon]}"
    )

    with st.spinner(f"Đang tải dữ liệu {ma_bien} từ máy chủ..."):
        ket_qua = doc_du_lieu_raster(ky_chay, ma_bien, han=han_chon)

    if ket_qua.get("loi"):
        st.warning(f"⚠️ {ket_qua['loi']}")
        return

    if ket_qua.get("thoi_gian_du_bao"):
        st.caption(f"Mốc thời gian trong file dữ liệu: {ket_qua['thoi_gian_du_bao']}")

    info = nhom_bien[ma_bien]
    fig = _ve_ban_do_netcdf(
        lon=ket_qua["lon"],
        lat=ket_qua["lat"],
        data=ket_qua["data"],
        ten_bien=info["ten"],
        don_vi=info["don_vi"],
        cmap=info["cmap"],
    )
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


@st.cache_resource(show_spinner=False)
def _bounds_tinh_netcdf():
    qn = doc_ranh_gioi_tinh()
    if qn is None:
        return None
    return qn.total_bounds  # [minx, miny, maxx, maxy]


def _ve_ban_do_netcdf(lon: np.ndarray, lat: np.ndarray, data: np.ndarray, ten_bien: str, don_vi: str, cmap: str):
    """
    Vẽ bản đồ raster chuẩn sai, mask theo ranh giới tỉnh, phủ ranh giới xã.
    Trước khi vẽ, dữ liệu được nội suy IDW (k-NN) + làm mịn Gaussian sang lưới mịn hơn
    (cùng phương pháp idw_knn() dùng cho bản đồ nội suy quan trắc), giúp bản đồ không
    bị "rỗ" theo từng ô lưới thô của mô hình.
    """
    # Mask theo tỉnh TRƯỚC khi nội suy: loại các điểm lưới ngoài Quảng Ninh (biển, tỉnh khác)
    # ra khỏi tập điểm dùng làm input cho IDW, tránh kéo giá trị sai lệch vào trong tỉnh.
    data_mask_truoc = mask_raster_theo_tinh(lon, lat, data)

    if np.all(np.isnan(data_mask_truoc)):
        fig, ax = plt.subplots(figsize=(9, 8))
        ax.text(0.5, 0.5, "Không có dữ liệu hợp lệ trong phạm vi tỉnh", ha="center", va="center")
        ax.set_axis_off()
        return fig

    ket_qua_min = noi_suy_idw_luoi_min(lon, lat, data_mask_truoc, grid_n=400, k=12, power=3.0, sigma=1.2)
    lon_min, lat_min, data_min = ket_qua_min["lon"], ket_qua_min["lat"], ket_qua_min["data"]

    # Mask theo tỉnh SAU khi nội suy: IDW có thể lan nhẹ giá trị ra ngoài biên tỉnh
    # (vì lưới mịn có điểm nằm sát biên), nên cắt lại cho khớp ranh giới thật.
    data_final = mask_raster_theo_tinh(lon_min, lat_min, data_min)

    gdf_xa = doc_shapefile_xa()
    bounds = _bounds_tinh_netcdf()

    fig, ax = plt.subplots(figsize=(9, 8))

    if np.all(np.isnan(data_final)):
        ax.text(0.5, 0.5, "Không có dữ liệu hợp lệ trong phạm vi tỉnh", ha="center", va="center")
        ax.set_axis_off()
        return fig

    vmax = np.nanmax(np.abs(data_final))
    vmax = vmax if vmax > 0 else 1.0
    pc = ax.pcolormesh(
        lon_min, lat_min, data_final,
        cmap=cmap, vmin=-vmax, vmax=vmax, shading="auto",
    )

    gdf_xa.boundary.plot(ax=ax, edgecolor="#333333", linewidth=0.4)

    qn = doc_ranh_gioi_tinh()
    if qn is not None:
        qn.boundary.plot(ax=ax, edgecolor="black", linewidth=1.3)

    if bounds is not None:
        pad = 0.05
        ax.set_xlim(bounds[0] - pad, bounds[2] + pad)
        ax.set_ylim(bounds[1] - pad, bounds[3] + pad)

    ax.set_axis_off()
    ax.set_title(f"{ten_bien}", fontsize=13, fontweight="bold")
    cbar = plt.colorbar(pc, ax=ax, shrink=0.7)
    cbar.set_label(f"Chuẩn sai ({don_vi})")

    fig.tight_layout()
    return fig
