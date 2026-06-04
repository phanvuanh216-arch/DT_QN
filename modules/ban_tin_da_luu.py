"""
modules/ban_tin_da_luu.py
Module BẢN TIN ĐÃ LƯU – quản lý và xem lại các bản tin đã tạo
"""
import streamlit as st
import json
from utils.data_fetcher import DOI_TUONG, KY_THANG, RISK_LABELS, RISK_COLORS, RISK_TEXT_COLORS


def render():
    st.markdown('<div class="module-header">💾 MODULE: Bản tin đã lưu</div>', unsafe_allow_html=True)

    ban_tin_list = st.session_state.get("ban_tin_list", [])

    if not ban_tin_list:
        st.info("Chưa có bản tin nào được lưu. Hãy vào **Truyền thông xã** để tạo bản tin.")
        return

    st.success(f"Có **{len(ban_tin_list)}** bản tin đã lưu.")

    # Bộ lọc
    col1, col2 = st.columns(2)
    with col1:
        xa_options = ["Tất cả"] + sorted(list({bt["xa"] for bt in ban_tin_list}))
        xa_filter = st.selectbox("Lọc theo xã:", xa_options)
    with col2:
        dt_options = ["Tất cả"] + sorted(list({bt["doi_tuong_name"] for bt in ban_tin_list}))
        dt_filter = st.selectbox("Lọc theo đối tượng:", dt_options)

    filtered = ban_tin_list
    if xa_filter != "Tất cả":
        filtered = [bt for bt in filtered if bt["xa"] == xa_filter]
    if dt_filter != "Tất cả":
        filtered = [bt for bt in filtered if bt["doi_tuong_name"] == dt_filter]

    st.markdown(f"Hiển thị **{len(filtered)}** bản tin.")
    st.markdown("---")

    for i, bt in enumerate(filtered):
        dt_info = DOI_TUONG.get(bt["doi_tuong_key"], {})
        icon = dt_info.get("icon", "📄")

        with st.expander(
            f"{icon} [{bt['created_at']}] Xã {bt['xa']} – {bt['doi_tuong_name']}",
            expanded=False,
        ):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**Xã:** {bt['xa']}  |  **Đối tượng:** {bt['doi_tuong_name']}  |  **Ngày tạo:** {bt['created_at']}")

            with col2:
                if st.button("✏️ Chỉnh sửa", key=f"edit_{bt['id']}", use_container_width=True):
                    st.session_state["edit_ban_tin"] = bt["id"]

            with col3:
                if st.button("🗑️ Xóa", key=f"del_{bt['id']}", use_container_width=True):
                    st.session_state["ban_tin_list"] = [b for b in ban_tin_list if b["id"] != bt["id"]]
                    st.rerun()

            # Hiển thị nhận định
            st.markdown("**Nhận định:**")
            st.markdown(bt["nhan_dinh"])

            # Nếu đang chỉnh sửa bản tin này
            if st.session_state.get("edit_ban_tin") == bt["id"]:
                new_nhan_dinh = st.text_area(
                    "Chỉnh sửa nhận định:",
                    value=bt["nhan_dinh"],
                    height=120,
                    key=f"edit_nd_{bt['id']}",
                )
                if st.button("💾 Lưu thay đổi", key=f"save_edit_{bt['id']}"):
                    for j, b in enumerate(st.session_state["ban_tin_list"]):
                        if b["id"] == bt["id"]:
                            st.session_state["ban_tin_list"][j]["nhan_dinh"] = new_nhan_dinh
                            break
                    st.session_state.pop("edit_ban_tin", None)
                    st.success("Đã lưu thay đổi!")
                    st.rerun()

            # Hiển thị bảng rủi ro thu gọn
            rr = bt.get("rui_ro_data", {})
            if rr:
                import pandas as pd
                _show_risk_summary(bt["doi_tuong_key"], rr)

    st.markdown("---")
    if st.button("🗑️ Xóa tất cả bản tin", type="secondary"):
        st.session_state["ban_tin_list"] = []
        st.rerun()


def _show_risk_summary(dt_key: str, rr_dict: dict):
    """Hiển thị tóm tắt rủi ro cao nhất theo kỳ."""
    import pandas as pd

    summary = {}
    for indicator, ky_vals in rr_dict.items():
        if isinstance(ky_vals, dict):
            for ky, val in ky_vals.items():
                if isinstance(val, int):
                    if ky not in summary or val > summary[ky]:
                        summary[ky] = val

    if summary:
        st.caption("📊 Mức rủi ro tổng hợp cao nhất theo kỳ:")
        cols = st.columns(len(KY_THANG))
        for col, ky in zip(cols, KY_THANG):
            val = summary.get(ky, 0)
            bg = RISK_COLORS.get(val, "#fff")
            fg = RISK_TEXT_COLORS.get(val, "#333")
            label = RISK_LABELS.get(val, "")
            col.markdown(
                f'<div style="text-align:center; background:{bg}; color:{fg}; '
                f'padding:4px; border-radius:4px; font-size:0.75rem; font-weight:bold;">'
                f'{ky}<br>{label}</div>',
                unsafe_allow_html=True,
            )
