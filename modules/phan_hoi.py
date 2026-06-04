"""
modules/phan_hoi.py
Module PHẢN HỒI – thu thập phản hồi từ người dùng
"""
import streamlit as st
from datetime import datetime


def render():
    st.markdown('<div class="module-header">💬 MODULE: Phản hồi</div>', unsafe_allow_html=True)
    st.markdown("Ghi nhận ý kiến từ cán bộ địa phương về chất lượng bản tin.")

    # ── Form phản hồi ─────────────────────────────────────────────────────────
    with st.form("feedback_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            xa = st.selectbox("🏘️ Xã:", ["Chọn xã..."] + _get_xa_list())
            ho_ten = st.text_input("👤 Họ và tên cán bộ:")
        with col2:
            chuc_vu = st.text_input("🏷️ Chức vụ:")
            doi_tuong = st.multiselect("🌱 Đối tượng liên quan:", ["Lúa", "Rau", "Lợn", "Gà"])

        st.markdown("---")
        chat_luong = st.slider("⭐ Đánh giá chất lượng bản tin:", 1, 5, 3)
        do_chinh_xac = st.radio(
            "📊 Mức độ chính xác dự báo:",
            ["Rất chính xác", "Chính xác", "Tương đối", "Chưa chính xác"],
            horizontal=True,
        )

        noi_dung = st.text_area(
            "📝 Nội dung phản hồi:",
            placeholder="Mô tả ý kiến, điều chỉnh, hoặc ghi nhận thực tế tại địa phương...",
            height=120,
        )

        de_xuat = st.text_area(
            "💡 Đề xuất cải tiến (nếu có):",
            placeholder="Gợi ý thêm loại rủi ro, cây trồng, vật nuôi...",
            height=80,
        )

        submitted = st.form_submit_button("📨 Gửi phản hồi", type="primary", use_container_width=True)

    if submitted:
        if xa == "Chọn xã..." or not ho_ten:
            st.error("Vui lòng chọn xã và nhập họ tên.")
        else:
            feedback = {
                "id": f"fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "xa": xa,
                "ho_ten": ho_ten,
                "chuc_vu": chuc_vu,
                "doi_tuong": doi_tuong,
                "chat_luong": chat_luong,
                "do_chinh_xac": do_chinh_xac,
                "noi_dung": noi_dung,
                "de_xuat": de_xuat,
                "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            if "feedback_list" not in st.session_state:
                st.session_state["feedback_list"] = []
            st.session_state["feedback_list"].append(feedback)
            st.success(f"✅ Cảm ơn **{ho_ten}**! Phản hồi của bạn đã được ghi nhận.")

    # ── Hiển thị phản hồi đã nhận ─────────────────────────────────────────────
    feedback_list = st.session_state.get("feedback_list", [])
    if feedback_list:
        st.markdown("---")
        st.markdown(f"### 📥 Phản hồi đã nhận ({len(feedback_list)})")

        # Thống kê nhanh
        avg_rating = sum(f["chat_luong"] for f in feedback_list) / len(feedback_list)
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng phản hồi", len(feedback_list))
        col2.metric("Đánh giá TB", f"⭐ {avg_rating:.1f}/5")
        col3.metric("Xã đã phản hồi", len(set(f["xa"] for f in feedback_list)))

        for fb in reversed(feedback_list):
            stars = "⭐" * fb["chat_luong"]
            with st.expander(f"[{fb['created_at']}] {fb['xa']} – {fb['ho_ten']} {stars}"):
                st.markdown(f"**Chức vụ:** {fb.get('chuc_vu', '')}  |  **Chính xác:** {fb['do_chinh_xac']}")
                if fb.get("doi_tuong"):
                    st.markdown(f"**Đối tượng:** {', '.join(fb['doi_tuong'])}")
                if fb.get("noi_dung"):
                    st.markdown(f"**Phản hồi:** {fb['noi_dung']}")
                if fb.get("de_xuat"):
                    st.markdown(f"**Đề xuất:** {fb['de_xuat']}")


def _get_xa_list():
    from utils.data_fetcher import XA_LIST
    return XA_LIST
