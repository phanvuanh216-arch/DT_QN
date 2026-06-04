"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
Cấu trúc module độc lập theo sơ đồ thiết kế
"""

import streamlit as st
import base64
import requests
from io import BytesIO
from PIL import Image
import numpy as np
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

# ─── Tải và xử lý logo (xóa nền trắng) ──────────────────────────────────────
@st.cache_data
def load_logo_base64():
    """Tải logo từ GitHub và xóa nền trắng, trả về base64 PNG."""
    try:
        url = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/logo_vien.jpg"
        resp = requests.get(url, timeout=10)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        data = np.array(img)
        # Xóa nền trắng/sáng: pixel nào R,G,B đều > 230 → alpha = 0
        r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
        white_mask = (r > 230) & (g > 230) & (b > 230)
        data[white_mask, 3] = 0
        result = Image.fromarray(data, "RGBA")
        buf = BytesIO()
        result.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

logo_b64 = load_logo_base64()
logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:72px;width:auto;object-fit:contain;" />'
    if logo_b64
    else '<div style="width:72px;height:72px;background:rgba(255,255,255,0.15);border-radius:8px;"></div>'
)

# ─── CSS tùy chỉnh ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Header cố định toàn cục ─────────────────────────────── */
    .site-header {
        background: linear-gradient(135deg, #1a6b3a 0%, #0f4d2a 60%, #0a3d1f 100%);
        border-bottom: 4px solid #f5a623;
        padding: 0 32px;
        display: flex;
        align-items: center;
        gap: 20px;
        min-height: 88px;
        margin: -1rem -1rem 1.5rem -1rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    }
    .site-header .logo-wrap {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 6px 10px;
    }
    .site-header .text-wrap {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 4px;
    }
    .site-header .line1 {
        color: #d4f0e0;
        font-size: 0.88rem;
        font-weight: 500;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        line-height: 1.3;
    }
    .site-header .line2 {
        color: #f5e642;
        font-size: 1.25rem;
        font-weight: 800;
        line-height: 1.25;
        text-shadow: 0 1px 4px rgba(0,0,0,0.4);
    }

    /* ── Các style gốc giữ nguyên ───────────────────────────── */
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
    .status-active  { background: #d4edda; border-left: 4px solid #28a745; }
    .status-warning { background: #fff3cd; border-left: 4px solid #ffc107; }
    .status-danger  { background: #f8d7da; border-left: 4px solid #dc3545; }
    .divider { border: none; border-top: 2px solid #e0e0e0; margin: 20px 0; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
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
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Header cố định – hiển thị trên mọi module ────────────────────────────────
st.markdown(f"""
<div class="site-header">
    <div class="logo-wrap">{logo_html}</div>
    <div class="text-wrap">
        <div class="line1">Viện Khoa học Khí tượng Thủy văn Môi trường và Biển</div>
        <div class="line2">Công cụ quản lý rủi ro khí hậu đối với cây trồng và vật nuôi trên địa bàn tỉnh Quảng Ninh</div>
    </div>
</div>
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
            "💬 Phản hồi",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("Đơn vị phát triển: Phòng Nghiên cứu Khí tượng nông nghiệp và Dịch vụ khí hậu")
    st.markdown("Viện Khoa học Khí tượng Thủy văn Môi trường và Biển")
    st.markdown("---")
    st.markdown("*Phiên bản 1.0 – 06/2026*")


# ─── Nội dung chính ────────────────────────────────────────────────────────────
if menu == "🏠 Tổng quan":
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏘️ Số xã", "30")
    col2.metric("🌱 Đối tượng nông nghiệp", "4")
    col3.metric("📅 Kỳ dự báo", "3 tháng")
    col4.metric("📄 Bản tin đã tạo", "0")

    st.markdown("---")
    st.markdown("### 📊 Luồng xử lý hệ thống")
    st.image("/mnt/user-data/uploads/1780451673991_image.png", use_container_width=True)

elif menu == "🔄 Dự báo khí hậu mùa":
    # Bỏ tiêu đề module, đẩy nội dung lên sát header
    du_bao_tu_dong.render()

elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":
    # Bỏ tiêu đề module, đẩy nội dung lên sát header
    ban_tin_xa.render()

    st.markdown("---")

    # Export bản tin và Bản tin đã lưu tích hợp vào đây
    tab_export, tab_saved = st.tabs(["📤 Export bản tin", "💾 Bản tin đã lưu"])
    with tab_export:
        export_ban_tin.render()
    with tab_saved:
        ban_tin_da_luu.render()

elif menu == "💬 Phản hồi":
    # Bỏ tiêu đề module, đẩy nội dung lên sát header
    phan_hoi.render()
