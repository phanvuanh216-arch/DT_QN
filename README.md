# 🌾 Bản tin Khí hậu Nông nghiệp Quảng Ninh

Hệ thống Streamlit hỗ trợ tạo, quản lý và xuất bản tin cảnh báo khí hậu cho 30 xã tại Quảng Ninh.

## Cấu trúc module

```
ban_tin_khi_hau/
├── app.py                    # Entry point Streamlit
├── requirements.txt
├── modules/
│   ├── du_bao_tu_dong.py    # Module: Dự báo tự động (tải từ server)
│   ├── ban_tin_xa.py         # Module: Truyền thông xã (tạo bản tin)
│   ├── ban_tin_da_luu.py     # Module: Bản tin đã lưu
│   ├── export_ban_tin.py     # Module: Export DOCX/JSON
│   └── phan_hoi.py           # Module: Phản hồi
└── utils/
    └── data_fetcher.py       # Tải dữ liệu từ http://222.254.32.10/forecast/Detai_QuangNinh/
```

## Cài đặt & Chạy cục bộ

```bash
# 1. Clone repo
git clone https://github.com/<your-username>/ban-tin-khi-hau-quang-ninh.git
cd ban-tin-khi-hau-quang-ninh

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Chạy
streamlit run app.py
```

## Deploy lên Streamlit Cloud

1. Push code lên GitHub (public hoặc private repo)
2. Vào [share.streamlit.io](https://share.streamlit.io)
3. **New app** → chọn repo → `app.py` → **Deploy**

> ⚠️ Đảm bảo server `http://222.254.32.10/forecast/Detai_QuangNinh/` cho phép request từ IP của Streamlit Cloud, hoặc mở public.

## Nguồn dữ liệu

- **Server dự báo:** `http://222.254.32.10/forecast/Detai_QuangNinh/`
- Khi không kết nối được server, hệ thống tự động dùng **dữ liệu demo** để không gián đoạn làm việc.

## Đối tượng nông nghiệp

| Module con | Đối tượng | Dịch hại/Bệnh |
|---|---|---|
| 🌾 Lúa | Lúa | Rầy, Sâu cuốn lá, Đục thân, Đạo ôn... |
| 🥬 Rau | Dưa chuột, Bắp cải, Súp lơ, Rau bí | Nhiều loại sâu bệnh |
| 🐖 Lợn | Lợn | Dịch tả, Tai xanh, Lở mồm long móng... |
| 🐓 Gà | Gà, Gia cầm | Cúm gia cầm, Newcastle, Cầu trùng... |

## Tính năng

- ✅ Tải dữ liệu dự báo tự động từ server
- ✅ Tạo bản tin riêng cho từng xã × từng đối tượng
- ✅ Bảng rủi ro màu sắc theo cấp (0–3)
- ✅ Nhận định tự động có thể chỉnh sửa
- ✅ Export bản tin ra file `.docx` theo mẫu chuẩn
- ✅ Lưu trữ và quản lý bản tin trong session
- ✅ Thu thập phản hồi từ cán bộ địa phương
# DT_QN
# DT_QN
