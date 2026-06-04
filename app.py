"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
Cấu trúc module độc lập theo sơ đồ thiết kế
"""

import streamlit as st
from modules import (
    du_bao_tu_dong,
    ban_tin_xa,
    ban_tin_da_luu,
    export_ban_tin,
    phan_hoi,
)

# ─── Cấu hình trang ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bản tin Khí hậu Quảng Ninh",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS tùy chỉnh ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .module-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .sub-module {
        background: #f0f4f8;
        border-left: 4px solid #2d6a4f;
        padding: 8px 14px;
        border-radius: 4px;
        margin: 4px 0;
        font-size: 0.95rem;
    }
    .status-active {
        background: #d4edda;
        border-left: 4px solid #28a745;
    }
    .status-warning {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    .status-danger {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    .divider {
        border: none;
        border-top: 2px solid #e0e0e0;
        margin: 20px 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #e8f4f8;
        border-radius: 6px 6px 0 0;
        padding: 8px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a5f !important;
        color: white !important;
    }
    .risk-0 { background-color: #ffffff; color: #333; }
    .risk-1 { background-color: #fffde7; color: #f57f17; font-weight: bold; }
    .risk-2 { background-color: #fff3e0; color: #e65100; font-weight: bold; }
    .risk-3 { background-color: #ffebee; color: #b71c1c; font-weight: bold; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #2d3748 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar – điều hướng ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌾 Bản tin Khí hậu")
    st.markdown("**Quảng Ninh – Nông nghiệp**")
    st.markdown("---")

    menu = st.radio(
        "📌 Chọn module:",
        [
            "🏠 Tổng quan",
            "🔄 Dự báo khí hậu mùa",
            "📋 Bản tin cảnh báo rủi ro khí hậu",
            "💾 Bản tin đã lưu",
            "📤 Export bản tin",
            "💬 Phản hồi",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**Nguồn dữ liệu:**")
    st.markdown("http://222.254.32.10/forecast/Detai_QuangNinh/")
    st.markdown("---")
    st.markdown("*Phiên bản 1.0 – 06/2026*")


# ─── Nội dung chính ────────────────────────────────────────────────────────────
if menu == "🏠 Tổng quan":
    st.title("🌾 Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh")
    st.markdown("""
    Hệ thống hỗ trợ tạo **bản tin cảnh báo khí hậu** cho các xã tại Quảng Ninh,
    bao gồm đánh giá rủi ro cho **Lúa, Rau, Lợn, Gà** theo từng kỳ tháng.
    """)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏘️ Số xã", "30")
    col2.metric("🌱 Đối tượng nông nghiệp", "4")
    col3.metric("📅 Kỳ dự báo", "3 tháng")
    col4.metric("📄 Bản tin đã tạo", "0")

    st.markdown("---")
    st.markdown("### 📊 Luồng xử lý hệ thống")
    st.image("/mnt/user-data/uploads/1780451673991_image.png", use_container_width=True)

elif menu == "🔄 Dự báo tự động":
    du_bao_tu_dong.render()

elif menu == "📋 Truyền thông xã (Bản tin)":
    ban_tin_xa.render()

elif menu == "💾 Bản tin đã lưu":
    ban_tin_da_luu.render()

elif menu == "📤 Export bản tin":
    export_ban_tin.render()

elif menu == "💬 Phản hồi":
    phan_hoi.render()
