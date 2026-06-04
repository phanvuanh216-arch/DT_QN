"""
Ứng dụng Streamlit - Hệ thống Bản tin Khí hậu Nông nghiệp Quảng Ninh
Cấu trúc module độc lập theo sơ đồ thiết kế
"""

import streamlit as st
import base64
import requests
from io import BytesIO
from PIL import Image, ImageFilter, ImageEnhance
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

# ─── Tải logo (giữ nguyên nền trắng) ─────────────────────────────────────────
@st.cache_data
def load_logo_base64():
    try:
        url = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/logo_vien.jpg"
        resp = requests.get(url, timeout=10)
        return base64.b64encode(resp.content).decode()
    except Exception:
        return None

# ─── Tải ảnh nền Quảng Ninh, làm mờ + tint xanh nhẹ ────────────────────────
@st.cache_data
def load_bg_base64():
    try:
        url = "https://raw.githubusercontent.com/phanvuanh216-arch/DT_QN/main/anh_dep_quang_ninh_giao_dien_1.jpg"
        resp = requests.get(url, timeout=15)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        # Resize để tăng tốc
        w, h = img.size
        img = img.resize((min(w, 1600), min(h, 900)), Image.LANCZOS)
        # Làm mờ Gaussian mạnh
        img = img.filter(ImageFilter.GaussianBlur(radius=14))
        # Giảm sáng xuống 55%
        img = ImageEnhance.Brightness(img).enhance(0.55)
        # Tint xanh lá nhẹ để hoà với giao diện
        overlay = Image.new("RGB", img.size, (8, 52, 25))
        img = Image.blend(img, overlay, alpha=0.28)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

logo_b64 = load_logo_base64()
bg_b64   = load_bg_base64()

logo_html = (
    f'<img src="data:image/jpeg;base64,{logo_b64}" '
    f'style="height:86px;width:auto;object-fit:contain;border-radius:6px;background:#fff;padding:4px;" />'
    if logo_b64
    else '<div style="width:86px;height:86px;background:#fff;border-radius:6px;"></div>'
)

bg_css = (
    f'background-image: url("data:image/jpeg;base64,{bg_b64}"); '
    f'background-size: cover; background-position: center top; background-attachment: fixed;'
    if bg_b64
    else 'background-color: #0d3320;'
)

# ─── CSS tùy chỉnh ────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    /* ── Ẩn chrome mặc định Streamlit ───────────────────────── */
    .block-container {{
        padding-top: 0 !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
        height: 0 !important;
        min-height: 0 !important;
    }}
    #MainMenu, footer {{ visibility: hidden; }}

    /* ── Ảnh nền toàn trang (vùng content) ──────────────────── */
    .stAppViewContainer > .main {{
        {bg_css}
    }}
    /* Lớp phủ mờ nhẹ để text dễ đọc */
    .stAppViewContainer > .main::before {{
        content: "";
        position: fixed;
        inset: 0;
        background: rgba(5, 30, 15, 0.18);
        pointer-events: none;
        z-index: 0;
    }}
    /* Đảm bảo nội dung nằm trên lớp phủ */
    .block-container {{ position: relative; z-index: 1; }}

    /* ── Header cố định toàn cục – full width ────────────────── */
    .site-header {{
        background: linear-gradient(135deg, #1a6b3a 0%, #0f4d2a 60%, #0a3d1f 100%);
        border-bottom: 4px solid #f5a623;
        padding: 14px 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 24px;
        min-height: 106px;
        margin: 0 -1rem 1.5rem -1rem;
        box-shadow: 0 4px 18px rgba(0,0,0,0.45);
    }}
    .site-header .logo-wrap {{
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        padding: 4px;
    }}
    .site-header .text-wrap {{
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 6px;
        text-align: center;
    }}
    .site-header .line1 {{
        color: #d4f0e0;
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        line-height: 1.3;
    }}
    .site-header .line2 {{
        color: #f5e642;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.3;
        text-shadow: 0 1px 5px rgba(0,0,0,0.5);
    }}

    /* ── Card / nội dung module – bán trong suốt ────────────── */
    div[data-testid="stVerticalBlock"] > div {{
        /* không override hết – chỉ để nền của widget tự xử lý */
    }}
    /* Các metric card, expander, dataframe có nền trắng bán trong suốt */
    [data-testid="metric-container"],
    [data-testid="stExpander"],
    .stDataFrame {{
        background: rgba(255,255,255,0.88) !important;
        border-radius: 8px;
        backdrop-filter: blur(4px);
    }}

    /* ── Ẩn thanh tiêu đề MODULE trong các module ───────────── */
    .module-header { display: none !important; }
    /* Ẩn đoạn mô tả ngay sau .module-header (dòng st.markdown text) */
    .module-header + div { display: none !important; }

    /* ── Ẩn thanh tiêu đề MODULE trong các module ──────────── */
    /* .module-header là class của thanh xanh đen "MODULE: ..." */
    .module-header {{ display: none !important; }}
    /* Ẩn đoạn text mô tả nằm ngay bên dưới .module-header */
    .module-header + div,
    .module-header ~ div:first-of-type {{ display: none !important; }}

    /* ── Các style gốc giữ nguyên ───────────────────────────── */
    .module-header {{
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
    }}
    .sub-module {{
        background: rgba(240,244,248,0.92);
        border-left: 4px solid #2d6a4f;
        padding: 8px 14px;
        border-radius: 4px;
        margin: 4px 0;
        font-size: 0.95rem;
    }}
    .status-active  {{ background: rgba(212,237,218,0.92); border-left: 4px solid #28a745; }}
    .status-warning {{ background: rgba(255,243,205,0.92); border-left: 4px solid #ffc107; }}
    .status-danger  {{ background: rgba(248,215,218,0.92); border-left: 4px solid #dc3545; }}
    .divider {{ border: none; border-top: 2px solid #e0e0e0; margin: 20px 0; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: rgba(232,244,248,0.92);
        border-radius: 6px 6px 0 0;
        padding: 8px 16px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: #1e3a5f !important;
        color: white !important;
    }}
    .risk-0 {{ background-color: rgba(255,255,255,0.9); color: #333; }}
    .risk-1 {{ background-color: rgba(255,253,231,0.92); color: #f57f17; font-weight: bold; }}
    .risk-2 {{ background-color: rgba(255,243,224,0.92); color: #e65100; font-weight: bold; }}
    .risk-3 {{ background-color: rgba(255,235,238,0.92); color: #b71c1c; font-weight: bold; }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #1e3a5f 0%, #2d3748 100%);
    }}
    [data-testid="stSidebar"] * {{ color: #e2e8f0 !important; }}
</style>
""", unsafe_allow_html=True)

# ─── JS: ẩn dòng mô tả nằm dưới thanh .module-header ───────────────────────────
st.markdown("""
<script>
(function hideModuleDesc() {
    function run() {
        document.querySelectorAll('.module-header').forEach(function(el) {
            // Ẩn phần tử cha chứa .module-header
            var parent = el.closest('[data-testid="stMarkdownContainer"]');
            if (parent) {
                // Lấy stVerticalBlock cha chứa cả header + description
                var block = parent.closest('[data-testid="stVerticalBlock"]');
                if (block) {
                    var children = Array.from(block.children);
                    var idx = children.findIndex(function(c) { return c.contains(el); });
                    // Ẩn phần tử ngay sau (description text)
                    if (idx >= 0 && children[idx + 1]) {
                        children[idx + 1].style.display = 'none';
                    }
                }
            }
        });
    }
    // Chạy ngay và sau 1s để đảm bảo DOM đã render
    run();
    setTimeout(run, 800);
    setTimeout(run, 2000);
})();
</script>
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
    col1.metric("🏘️ Số xã", "28")
    col2.metric("🌱 Đối tượng nông nghiệp", "4")
    col3.metric("📅 Kỳ dự báo", "Từ 1 - 3 tháng")
    col4.metric("📄 Bản tin đã tạo", "0")

    st.markdown("---")
    st.markdown("### 📊 Luồng xử lý hệ thống")
    st.image("/mnt/user-data/uploads/1780451673991_image.png", use_container_width=True)

elif menu == "🔄 Dự báo khí hậu mùa":
    du_bao_tu_dong.render()

elif menu == "📋 Bản tin cảnh báo rủi ro khí hậu":
    ban_tin_xa.render()

    st.markdown("---")

    tab_export, tab_saved = st.tabs(["📤 Export bản tin", "💾 Bản tin đã lưu"])
    with tab_export:
        export_ban_tin.render()
    with tab_saved:
        ban_tin_da_luu.render()

elif menu == "💬 Phản hồi":
    phan_hoi.render()
