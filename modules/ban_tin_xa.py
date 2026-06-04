"""
modules/ban_tin_xa.py
Module TRUYỀN THÔNG XÃ – tạo bản tin cho từng xã và từng đối tượng nông nghiệp
"""
import streamlit as st
import json
from datetime import datetime
from utils.data_fetcher import (
    XA_LIST, KY_THANG, DOI_TUONG, load_data_for_xa,
    RISK_LABELS, RISK_COLORS, RISK_TEXT_COLORS,
)


def render():
    st.markdown('<div class="module-header">📋 MODULE: Truyền thông xã (Bản tin)</div>', unsafe_allow_html=True)

    # ── Chọn xã ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        xa_chon = st.selectbox("🏘️ Chọn xã:", XA_LIST, key="bt_xa_sel")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("📥 Tải dữ liệu xã", use_container_width=True)

    # Tải dữ liệu (từ cache hoặc server)
    cache = st.session_state.get("forecast_cache", {})
    if xa_chon in cache:
        data = cache[xa_chon]
        source = "📦 Session cache"
    else:
        with st.spinner("Đang tải..."):
            data, source = load_data_for_xa(xa_chon)

    st.info(f"**Xã:** {xa_chon} | **Nguồn:** {source}")

    # ── Tab cho từng đối tượng ────────────────────────────────────────────────
    tabs = st.tabs(["🌾 Lúa", "🥬 Rau", "🐖 Lợn", "🐓 Gà"])

    doi_tuong_keys = ["lua", "rau", "lon", "ga"]
    for tab, dt_key in zip(tabs, doi_tuong_keys):
        with tab:
            _render_doi_tuong_module(xa_chon, dt_key, data)


def _render_doi_tuong_module(xa_name: str, dt_key: str, data: dict):
    """Module con độc lập cho từng đối tượng."""
    dt_info = DOI_TUONG[dt_key]
    icon = dt_info["icon"]
    name = dt_info["name"]
    rui_ro_data = data.get("rui_ro", {}).get(dt_key, {})
    du_bao = data.get("du_bao_thang", {})

    st.markdown(f"### {icon} Bản tin rủi ro khí hậu – **{name}**")
    st.markdown(f"**Xã {xa_name}** | Giai đoạn Tháng 6 đến Tháng 8 năm 2026")
    st.markdown("---")

    # ── Dự báo khí hậu ────────────────────────────────────────────────────────
    with st.expander("📊 Dự báo khí hậu tháng 6–8", expanded=True):
        _render_du_bao_thang(du_bao)

    # ── Bảng rủi ro ───────────────────────────────────────────────────────────
    if dt_key == "rau":
        for loai_key, loai_info in dt_info["loai_rau"].items():
            with st.expander(f"🌿 Rủi ro {loai_info['name']}", expanded=True):
                loai_rr = rui_ro_data.get(loai_key, {})
                _render_risk_section(
                    xa_name, loai_info["name"], loai_rr,
                    dt_info["rui_ro_khi_hau"],
                    loai_info["dich_hai"],
                    loai_info.get("chu_ky", {}),
                )
    else:
        with st.expander(f"⚠️ Bảng rủi ro {name}", expanded=True):
            _render_risk_section(
                xa_name, name, rui_ro_data,
                dt_info.get("rui_ro_khi_hau", []),
                dt_info.get("dich_hai", dt_info.get("dich_benh", [])),
                dt_info.get("chu_ky", {}),
            )

    # ── Soạn thảo nhận định ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✏️ Nhận định và khuyến cáo")
    nhan_dinh_default = _generate_nhan_dinh(xa_name, name, rui_ro_data)
    nhan_dinh = st.text_area(
        "Nội dung nhận định (có thể chỉnh sửa):",
        value=nhan_dinh_default,
        height=150,
        key=f"nd_{xa_name}_{dt_key}",
    )

    # ── Lưu bản tin ───────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"💾 Lưu bản tin {name}", key=f"save_{xa_name}_{dt_key}", use_container_width=True):
            _save_ban_tin(xa_name, dt_key, name, rui_ro_data, nhan_dinh, du_bao)
    with col2:
        if st.button(f"👁️ Xem trước bản tin", key=f"preview_{xa_name}_{dt_key}", use_container_width=True):
            st.session_state[f"preview_{xa_name}_{dt_key}"] = True

    if st.session_state.get(f"preview_{xa_name}_{dt_key}"):
        _preview_ban_tin(xa_name, name, icon, du_bao, rui_ro_data, nhan_dinh, dt_info, dt_key)


def _render_du_bao_thang(du_bao: dict):
    """Hiển thị bảng dự báo nhiệt độ & lượng mưa."""
    import pandas as pd

    rows_nt, rows_lm = [], []
    for ky in KY_THANG:
        d = du_bao.get(ky, {})
        nt = d.get("nhiet_do", {})
        lm = d.get("luong_mua", {})
        rows_nt.append({"Kỳ": ky, "Thấp hơn (%)": nt.get("thap_hon", ""), "Xấp xỉ (%)": nt.get("xap_xi", ""), "Cao hơn (%)": nt.get("cao_hon", "")})
        rows_lm.append({"Kỳ": ky, "Thấp hơn (%)": lm.get("thap_hon", ""), "Xấp xỉ (%)": lm.get("xap_xi", ""), "Cao hơn (%)": lm.get("cao_hon", "")})

    c1, c2 = st.columns(2)
    with c1:
        st.caption("🌡️ Nhiệt độ")
        st.dataframe(pd.DataFrame(rows_nt).set_index("Kỳ"), use_container_width=True)
    with c2:
        st.caption("🌧️ Lượng mưa")
        st.dataframe(pd.DataFrame(rows_lm).set_index("Kỳ"), use_container_width=True)


def _render_risk_section(xa, name, rr_dict, rui_ro_kh, dich_hai_list, chu_ky):
    """Hiển thị bảng rủi ro màu sắc."""
    import pandas as pd

    rows = []
    if chu_ky:
        rows.append({"Chỉ tiêu": "Chu kỳ sinh trưởng", **{ky: chu_ky.get(ky, "") for ky in KY_THANG}})

    st.caption("🌦️ Rủi ro khí hậu")
    kh_rows = [{"Chỉ tiêu": rr, **{ky: rr_dict.get(rr, {}).get(ky, 0) for ky in KY_THANG}} for rr in rui_ro_kh]
    if chu_ky:
        kh_rows = [rows[0]] + kh_rows
    _styled_df(kh_rows)

    if dich_hai_list:
        st.caption("🦟 Rủi ro sinh vật hại / dịch bệnh")
        dh_rows = [{"Chỉ tiêu": dh, **{ky: rr_dict.get(dh, {}).get(ky, 0) for ky in KY_THANG}} for dh in dich_hai_list]
        _styled_df(dh_rows)


def _styled_df(rows: list):
    import pandas as pd
    if not rows:
        return
    df = pd.DataFrame(rows).set_index("Chỉ tiêu")
    int_cols = [c for c in df.columns if c in KY_THANG]

    def color_cell(val):
        if isinstance(val, int):
            bg = RISK_COLORS.get(val, "#fff")
            fg = RISK_TEXT_COLORS.get(val, "#333")
            return f"background-color: {bg}; color: {fg}; font-weight: bold;"
        return ""

    styled = df.style.applymap(color_cell, subset=int_cols)
    # Show label text instead of numbers
    label_df = df.copy()
    for col in int_cols:
        label_df[col] = label_df[col].apply(
            lambda v: RISK_LABELS.get(v, v) if isinstance(v, int) else v
        )
    label_styled = label_df.style.applymap(color_cell, subset=int_cols)
    st.dataframe(label_styled, use_container_width=True, height=min(350, 55 + 35 * len(rows)))


def _generate_nhan_dinh(xa: str, doi_tuong: str, rr_dict: dict) -> str:
    """Tự động tạo nhận định dựa trên dữ liệu rủi ro."""
    max_risk = 0
    for indicator, ky_vals in rr_dict.items():
        if isinstance(ky_vals, dict):
            for ky, val in ky_vals.items():
                if isinstance(val, int) and val > max_risk:
                    max_risk = val

    if max_risk == 0:
        level = "thấp, không đáng lo ngại"
    elif max_risk == 1:
        level = "ở mức cấp 1, cần theo dõi"
    elif max_risk == 2:
        level = "ở mức cấp 2, cần chú ý phòng ngừa"
    else:
        level = "ở mức cấp 3, cần cảnh báo khẩn cấp"

    return (
        f"Trong giai đoạn tháng 6 đến tháng 8 năm 2026, rủi ro khí hậu đối với {doi_tuong} "
        f"tại xã {xa} {level}.\n\n"
        f"Khuyến cáo: Nông dân cần theo dõi chặt chẽ diễn biến thời tiết, áp dụng các biện pháp "
        f"kỹ thuật phù hợp với từng giai đoạn sinh trưởng, và liên hệ với cán bộ khuyến nông "
        f"khi có dấu hiệu bất thường."
    )


def _save_ban_tin(xa, dt_key, dt_name, rr_data, nhan_dinh, du_bao):
    """Lưu bản tin vào session state."""
    if "ban_tin_list" not in st.session_state:
        st.session_state["ban_tin_list"] = []

    ban_tin = {
        "id": f"{xa}_{dt_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "xa": xa,
        "doi_tuong_key": dt_key,
        "doi_tuong_name": dt_name,
        "nhan_dinh": nhan_dinh,
        "rui_ro_data": rr_data,
        "du_bao": du_bao,
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    # Ghi đè nếu đã có bản tin cùng xã + đối tượng
    existing = [i for i, bt in enumerate(st.session_state["ban_tin_list"])
                if bt["xa"] == xa and bt["doi_tuong_key"] == dt_key]
    if existing:
        st.session_state["ban_tin_list"][existing[0]] = ban_tin
    else:
        st.session_state["ban_tin_list"].append(ban_tin)

    st.success(f"✅ Đã lưu bản tin **{dt_name}** cho xã **{xa}**!")
    st.rerun()


def _preview_ban_tin(xa, name, icon, du_bao, rr_data, nhan_dinh, dt_info, dt_key):
    """Hiển thị preview bản tin dạng văn bản."""
    st.markdown("---")
    st.markdown("#### 📄 XEM TRƯỚC BẢN TIN")
    preview_md = f"""
---
## BẢN TIN CẢNH BÁO KHÍ HẬU THÁNG 6-8/2026
### {icon} {name.upper()} – XÃ {xa.upper()}

**Dự báo khí hậu tháng 6 đến tháng 8/2026**

| Kỳ | Nhiệt độ (Thấp/Xấp xỉ/Cao) | Lượng mưa (Thấp/Xấp xỉ/Cao) |
|---|---|---|
"""
    for ky in KY_THANG:
        d = du_bao.get(ky, {})
        nt = d.get("nhiet_do", {})
        lm = d.get("luong_mua", {})
        nt_str = f"{nt.get('thap_hon','')}%/{nt.get('xap_xi','')}%/{nt.get('cao_hon','')}%"
        lm_str = f"{lm.get('thap_hon','')}%/{lm.get('xap_xi','')}%/{lm.get('cao_hon','')}%"
        preview_md += f"| {ky} | {nt_str} | {lm_str} |\n"

    preview_md += f"\n**Nhận định và khuyến cáo:**\n\n{nhan_dinh}\n\n---"
    st.markdown(preview_md)

    if st.button("❌ Đóng xem trước", key=f"close_preview_{xa}_{dt_key}"):
        st.session_state[f"preview_{xa}_{dt_key}"] = False
        st.rerun()
