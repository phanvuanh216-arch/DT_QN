"""
modules/du_bao_tu_dong.py
Module DỰ BÁO TỰ ĐỘNG – tải và hiển thị dữ liệu dự báo từ server
"""
import streamlit as st
import pandas as pd
from utils.data_fetcher import XA_LIST, KY_THANG, load_data_for_xa, DOI_TUONG


def render():
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

    styled = df.style.applymap(color_cell, subset=ky_list)
    st.dataframe(styled, use_container_width=True, height=min(250, 50 + 35 * len(rows)))
