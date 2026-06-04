"""
utils/data_fetcher.py
Tải dữ liệu dự báo từ server http://222.254.32.10/forecast/Detai_QuangNinh/
"""
import requests
import json
import os
import streamlit as st
from datetime import datetime

BASE_URL = "http://222.254.32.10/forecast/Detai_QuangNinh/"

# Mapping tên xã → slug trên server (điều chỉnh theo cấu trúc thực tế của server)
XA_LIST = [
    "Quảng Hà", "Quảng Điền", "Quảng Thắng", "Quảng Thành", "Quảng Chính",
    "Quảng Long", "Quảng Phong", "Quảng Minh", "Quảng Trung", "Quảng Tân",
    "Quảng Nghĩa", "Quảng Hợp", "Quảng Tiến", "Quảng Đức", "Quảng Lợi",
    "Quảng An", "Quảng Sơn", "Quảng Bình", "Quảng Yên", "Quảng Đông",
    "Đầm Hà", "Hạ Long", "Móng Cái", "Cẩm Phả", "Tiên Yên",
    "Bình Liêu", "Vân Đồn", "Cô Tô", "Ba Chẽ", "Hoành Bồ"
]

DOI_TUONG = {
    "lua": {
        "name": "Lúa",
        "icon": "🌾",
        "color": "#f59e0b",
        "chu_ky": {
            "T1/6": "Thu hoạch", "T2/6": "Thu hoạch", "T3/6": "Gieo, nảy mầm",
            "T1/7": "Mạ", "T2/7": "Mạ", "T3/7": "Đẻ nhánh",
            "T1/8": "Đẻ nhánh", "T2/8": "Làm đòng", "T3/8": "Phân hóa hoa",
        },
        "rui_ro_khi_hau": ["Rủi ro hạn hán", "Rủi ro nắng nóng/ giá lạnh", "Rủi ro mưa lớn"],
        "dich_hai": ["Rầy", "Sâu cuốn lá", "Đục thân", "Đạo ôn", "Nấm cổ bông", "Khô vằn", "Rầy nâu"],
    },
    "rau": {
        "name": "Rau",
        "icon": "🥬",
        "color": "#10b981",
        "rui_ro_khi_hau": ["Rủi ro hạn hán", "Rủi ro nắng nóng/ giá lạnh", "Rủi ro mưa lớn"],
        "loai_rau": {
            "dua_chuot": {
                "name": "Dưa chuột",
                "chu_ky": {
                    "T1/7": "Nảy mầm", "T2/7": "Cây con", "T3/7": "Thân lá",
                    "T1/8": "Thân lá", "T2/8": "Ra hoa", "T3/8": "Ra hoa",
                },
                "dich_hai": ["Thối thân", "Nứt thân", "Bọ phấn trắng", "Bọ trĩ", "Sương mai"],
            },
            "bap_cai": {
                "name": "Bắp cải",
                "chu_ky": {"T2/8": "Nảy mầm", "T3/8": "Cây con"},
                "dich_hai": ["Sâu xanh", "Rệp", "Sâu tơ", "Sâu đen"],
            },
            "sup_lo": {
                "name": "Súp lơ",
                "chu_ky": {
                    "T1/7": "Nảy mầm", "T2/7": "Cây con", "T3/7": "Cây con",
                    "T1/8": "Hồi xanh", "T2/8": "Trải lá bàng", "T3/8": "Trải lá bàng",
                },
                "dich_hai": ["Thối gốc", "Sâu tơ", "Sâu xanh", "Sâu khoang", "Đốm trắng"],
            },
            "rau_bi": {
                "name": "Rau bí",
                "chu_ky": {
                    "T2/7": "Nảy mầm", "T3/7": "Cây con",
                    "T1/8": "Thân lá", "T2/8": "Thân lá", "T3/8": "Thân lá",
                },
                "dich_hai": ["Thối gốc", "Sâu tơ", "Sâu xanh", "Sâu khoang", "Đốm trắng"],
            },
        },
    },
    "lon": {
        "name": "Lợn",
        "icon": "🐖",
        "color": "#ec4899",
        "rui_ro_khi_hau": ["Rủi ro nắng nóng/ giá lạnh", "Rủi ro mưa lớn"],
        "dich_benh": [
            "Dịch tả lợn Châu Phi", "Dịch tả lợn cổ điển", "Viêm phổi dính sườn",
            "Suyễn lợn", "Tai xanh", "Cúm lợn", "Tiêu chảy do E. coli",
            "Sưng mặt, phù đầu", "Đóng dấu lợn", "Phó Thương hàn lợn",
            "Viêm não nhật bản", "Lở mồm long móng", "Tụ huyết trùng lợn",
        ],
    },
    "ga": {
        "name": "Gà",
        "icon": "🐓",
        "color": "#8b5cf6",
        "rui_ro_khi_hau": ["Rủi ro nắng nóng/ giá lạnh", "Rủi ro mưa lớn"],
        "dich_benh": [
            "Hen gà", "Cúm gia cầm độc lực cao", "Cầu trùng gà",
            "Viêm ruột hoại tử", "Đại tràng (Ecoli)", "Thương hàn gà",
            "Newcastle", "Tụ huyết trùng gia cầm", "Bệnh Marek (nổi cục)",
            "Ký sinh trùng đường máu", "Đậu gà (mò)",
        ],
    },
}

KY_THANG = ["T1/6", "T2/6", "T3/6", "T1/7", "T2/7", "T3/7", "T1/8", "T2/8", "T3/8"]

RISK_LABELS = {0: "Không", 1: "Cấp 1", 2: "Cấp 2", 3: "Cấp 3"}
RISK_COLORS = {0: "#ffffff", 1: "#fff9c4", 2: "#ffcc80", 3: "#ef9a9a"}
RISK_TEXT_COLORS = {0: "#555", 1: "#f57f17", 2: "#e65100", 3: "#b71c1c"}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forecast_data(xa_slug: str) -> dict | None:
    """Tải dữ liệu dự báo từ server cho 1 xã. Trả về dict hoặc None nếu lỗi."""
    url = f"{BASE_URL}{xa_slug}/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        return None


def get_demo_data(xa_name: str) -> dict:
    """
    Trả về dữ liệu demo khi không kết nối được server.
    Cấu trúc khớp với format dữ liệu thực từ server.
    """
    import random
    random.seed(hash(xa_name) % 1000)

    def rand_risk():
        return random.choice([0, 1, 2, 3])

    data = {
        "xa": xa_name,
        "generated_at": datetime.now().isoformat(),
        "source": "demo",
        "du_bao_thang": {},
        "rui_ro": {},
    }

    for ky in KY_THANG:
        month = int(ky.split("/")[1])
        data["du_bao_thang"][ky] = {
            "nhiet_do": {
                "thap_hon": random.randint(5, 20),
                "xap_xi": random.randint(25, 40),
                "cao_hon": 100 - random.randint(30, 65),
                "nhan_dinh": "Nhiệt độ có xu hướng cao hơn trung bình nhiều năm.",
            },
            "luong_mua": {
                "thap_hon": random.randint(5, 25),
                "xap_xi": random.randint(25, 40),
                "cao_hon": random.randint(15, 50),
                "nhan_dinh": "Lượng mưa xấp xỉ hoặc thấp hơn trung bình nhiều năm.",
            },
        }

    for doi_tuong_key in ["lua", "lon", "ga"]:
        dt = DOI_TUONG[doi_tuong_key]
        data["rui_ro"][doi_tuong_key] = {}
        for rr in dt.get("rui_ro_khi_hau", []):
            data["rui_ro"][doi_tuong_key][rr] = {ky: rand_risk() for ky in KY_THANG}
        for dh in dt.get("dich_hai", dt.get("dich_benh", [])):
            data["rui_ro"][doi_tuong_key][dh] = {ky: rand_risk() for ky in KY_THANG}

    # Rau – theo từng loại rau
    data["rui_ro"]["rau"] = {}
    for loai_key, loai in DOI_TUONG["rau"]["loai_rau"].items():
        data["rui_ro"]["rau"][loai_key] = {}
        for rr in DOI_TUONG["rau"]["rui_ro_khi_hau"]:
            data["rui_ro"]["rau"][loai_key][rr] = {ky: rand_risk() for ky in KY_THANG}
        for dh in loai["dich_hai"]:
            data["rui_ro"]["rau"][loai_key][dh] = {ky: rand_risk() for ky in KY_THANG}

    return data


def load_data_for_xa(xa_name: str) -> tuple[dict, str]:
    """
    Load dữ liệu cho 1 xã. Trả về (data_dict, source_label).
    source_label: 'server' hoặc 'demo'
    """
    xa_slug = xa_name.lower().replace(" ", "_").replace("ả", "a").replace("ắ", "a")
    server_data = fetch_forecast_data(xa_slug)
    if server_data:
        return server_data, "🟢 Server thực"
    return get_demo_data(xa_name), "🟡 Dữ liệu demo"
