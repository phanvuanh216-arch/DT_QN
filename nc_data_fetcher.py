"""
utils/nc_data_fetcher.py
Tải & xử lý dữ liệu chuẩn sai khí hậu mùa (.nc) từ server nội bộ:
    http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/

Cấu trúc trên server:
    domain_d02/
        202211/   202212/   ...   202606/      <- thư mục đặt tên YYYYMM (kỳ chạy mô hình)
            ano.T2m.<YYYYMM>.nc
            ano.Tx.<YYYYMM>.nc
            ano.Tm.<YYYYMM>.nc
            ano.R.<YYYYMM>.nc
            ano.RH2m.<YYYYMM>.nc
            ano.CDD.<YYYYMM>.nc
            ano.CWD.<YYYYMM>.nc
            ano.Evap.<YYYYMM>.nc
            ano.FD13.<YYYYMM>.nc
            ano.FD15.<YYYYMM>.nc
            ano.Rx1day.<YYYYMM>.nc
            ano.Rx5day.<YYYYMM>.nc
            ano.SU35.<YYYYMM>.nc
            ano.SU37.<YYYYMM>.nc
            ano.SU39.<YYYYMM>.nc

Mỗi file .nc có 6 timestep (hạn dự báo tháng 1 -> tháng 6 kể từ kỳ chạy),
nhưng ứng dụng chỉ dùng 3 timestep đầu (hạn dự báo tới 3 tháng) theo yêu cầu nghiệp vụ.

Lưu ý: dùng netCDF4 thuần (đã có sẵn trong requirements.txt) để đọc file .nc
trực tiếp từ bytes trong RAM (tham số memory=...), không cần cài thêm xarray/h5netcdf.
"""
from __future__ import annotations

import re

import numpy as np
import requests
import streamlit as st
import netCDF4 as nc


BASE_URL = "http://222.254.32.10/forecast/Detai_QuangNinh/domain_d02/"
HAN_DU_BAO_MAX = 3  # chỉ dùng tới hạn dự báo 3 tháng (yêu cầu nghiệp vụ)
TIMEOUT_LIST = 15
TIMEOUT_FILE = 60

SHAPEFILE_XA = "shp/QN_XA_FINAL.shp"
SHAPEFILE_TINH = "shp/RG_34TINH.dbf"
TEN_TINH = "Quảng Ninh"

# ─── Định nghĩa 2 nhóm biến ─────────────────────────────────────────────────
NHOM_KHI_HAU = {
    "T2m": {"ten": "Nhiệt độ trung bình (T2m)", "don_vi": "°C", "cmap": "RdBu_r"},
    "Tx": {"ten": "Nhiệt độ tối cao (Tx)", "don_vi": "°C", "cmap": "RdBu_r"},
    "Tm": {"ten": "Nhiệt độ tối thấp (Tm)", "don_vi": "°C", "cmap": "RdBu_r"},
    "R": {"ten": "Lượng mưa (R)", "don_vi": "mm", "cmap": "BrBG"},
    "RH2m": {"ten": "Độ ẩm tương đối (RH2m)", "don_vi": "%", "cmap": "BrBG"},
}

NHOM_CUC_DOAN = {
    "CDD": {"ten": "Số ngày khô liên tục (CDD)", "don_vi": "ngày", "cmap": "BrBG"},
    "CWD": {"ten": "Số ngày ẩm liên tục (CWD)", "don_vi": "ngày", "cmap": "BrBG_r"},
    "Evap": {"ten": "Lượng bốc hơi (Evap)", "don_vi": "mm", "cmap": "BrBG"},
    "FD13": {"ten": "Số ngày rét hại < 13°C (FD13)", "don_vi": "ngày", "cmap": "RdBu"},
    "FD15": {"ten": "Số ngày rét < 15°C (FD15)", "don_vi": "ngày", "cmap": "RdBu"},
    "Rx1day": {"ten": "Lượng mưa lớn nhất 1 ngày (Rx1day)", "don_vi": "mm", "cmap": "BrBG"},
    "Rx5day": {"ten": "Lượng mưa lớn nhất 5 ngày (Rx5day)", "don_vi": "mm", "cmap": "BrBG"},
    "SU35": {"ten": "Số ngày nắng nóng > 35°C (SU35)", "don_vi": "ngày", "cmap": "RdBu_r"},
    "SU37": {"ten": "Số ngày nắng nóng > 37°C (SU37)", "don_vi": "ngày", "cmap": "RdBu_r"},
    "SU39": {"ten": "Số ngày nắng nóng > 39°C (SU39)", "don_vi": "ngày", "cmap": "RdBu_r"},
}

# Regex khớp directory-listing kiểu Apache mod_autoindex / Nginx autoindex:
#   <a href="202606/">202606/</a>
_RE_THU_MUC_YYYYMM = re.compile(r'href=["\']((\d{6})/?)["\']')


# ─── 1. Liệt kê các kỳ chạy (thư mục YYYYMM) có trên server ────────────────
@st.cache_data(ttl=900, show_spinner=False)
def lay_danh_sach_ky_chay() -> list[str]:
    """
    Parse trang directory-listing tại BASE_URL để lấy danh sách kỳ chạy
    (thư mục dạng YYYYMM), sắp xếp giảm dần (mới nhất trước).
    Trả về [] nếu không kết nối được hoặc không parse được thư mục nào.
    """
    try:
        resp = requests.get(BASE_URL, timeout=TIMEOUT_LIST)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return []

    matches = _RE_THU_MUC_YYYYMM.findall(resp.text)
    ky_chay_set = set()
    for _, yyyymm in matches:
        if 1 <= int(yyyymm[4:6]) <= 12:  # lọc hợp lệ: tháng 01-12
            ky_chay_set.add(yyyymm)

    return sorted(ky_chay_set, reverse=True)


# ─── 2. Sinh nhãn hạn dự báo (tháng 1 / 2 / 3 kể từ kỳ chạy) ────────────────
def sinh_nhan_han_du_bao(ky_chay: str) -> list[tuple[int, str]]:
    """
    Trả về list (han, nhan_hien_thi) cho hạn dự báo 1..HAN_DU_BAO_MAX tháng kể từ kỳ chạy.
    Ví dụ ky_chay='202606' -> hạn 1 = 'Tháng 07/2026', hạn 2 = 'Tháng 08/2026', hạn 3 = 'Tháng 09/2026'.
    `han` (1-based) dùng để chọn timestep tương ứng trong file .nc (timestep 0-based = han - 1).
    """
    nam = int(ky_chay[:4])
    thang = int(ky_chay[4:6])
    nhan = []
    for han in range(1, HAN_DU_BAO_MAX + 1):
        t = thang + han
        y = nam + (t - 1) // 12
        m = (t - 1) % 12 + 1
        nhan.append((han, f"Tháng {m:02d}/{y}"))
    return nhan


def dinh_dang_ky_chay(ky_chay: str) -> str:
    """'202606' -> 'Tháng 06/2026' (dùng hiển thị 'thời gian phân tích')."""
    return f"Tháng {ky_chay[4:6]}/{ky_chay[:4]}"


# ─── 3. Tải file .nc của 1 biến trong 1 kỳ chạy ─────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def tai_file_nc(ky_chay: str, ma_bien: str) -> bytes | None:
    """Tải file ano.<ma_bien>.<ky_chay>.nc từ server, trả về bytes hoặc None nếu lỗi."""
    url = f"{BASE_URL}{ky_chay}/ano.{ma_bien}.{ky_chay}.nc"
    try:
        resp = requests.get(url, timeout=TIMEOUT_FILE)
        resp.raise_for_status()
        return resp.content
    except requests.exceptions.RequestException:
        return None


# ─── 4. Đọc dữ liệu raster (lon, lat, mảng giá trị) cho 1 hạn dự báo ───────
def doc_du_lieu_raster(ky_chay: str, ma_bien: str, han: int) -> dict:
    """
    Trả về dict {
        'lon': np.ndarray (1D),
        'lat': np.ndarray (1D),
        'data': np.ndarray 2D (lat, lon) - đã thay missing -> NaN,
        'thoi_gian_du_bao': str | None  (đã format sẵn, vd '2026-07-15'),
        'loi': None | str
    }
    han: 1..HAN_DU_BAO_MAX (hạn dự báo tính theo tháng kể từ kỳ chạy)
    """
    raw = tai_file_nc(ky_chay, ma_bien)
    if raw is None:
        return {"loi": (
            f"Không tải được file ano.{ma_bien}.{ky_chay}.nc từ server. "
            f"Kiểm tra kết nối tới {BASE_URL}{ky_chay}/ hoặc tên file/biến."
        )}

    try:
        ds = nc.Dataset(f"inmemory_{ky_chay}_{ma_bien}.nc", memory=raw)
    except Exception as exc:
        return {"loi": f"Không đọc được file NetCDF (file lỗi hoặc không đúng định dạng): {exc}"}

    try:
        bien_ten = ma_bien if ma_bien in ds.variables else None
        if bien_ten is None:
            ung_vien = [v for v in ds.variables if v not in ("lon", "lat", "time", "longitude", "latitude")]
            if not ung_vien:
                return {"loi": f"Không tìm thấy biến '{ma_bien}' trong file NetCDF."}
            bien_ten = ung_vien[0]

        var = ds.variables[bien_ten]

        ts_index = han - 1  # 0-based
        n_time = var.shape[0] if "time" in var.dimensions else 1
        if ts_index >= n_time:
            return {"loi": f"File chỉ có {n_time} hạn dự báo, không có hạn thứ {han}."}

        lat_name = "lat" if "lat" in ds.variables else ("latitude" if "latitude" in ds.variables else None)
        lon_name = "lon" if "lon" in ds.variables else ("longitude" if "longitude" in ds.variables else None)
        if lat_name is None or lon_name is None:
            return {"loi": "Không tìm thấy biến tọa độ lat/lon trong file NetCDF."}

        if "time" in var.dimensions:
            gia_tri = np.asarray(var[ts_index, :, :], dtype="float64")
        else:
            gia_tri = np.asarray(var[:, :], dtype="float64")

        if np.ma.is_masked(gia_tri) or isinstance(gia_tri, np.ma.MaskedArray):
            mask = np.ma.getmaskarray(gia_tri)
            gia_tri = np.ma.filled(gia_tri, np.nan)
            gia_tri[mask] = np.nan

        # Phòng trường hợp giá trị fill không được netCDF4 tự nhận làm mask
        # (ví dụ thiếu khai báo chuẩn _FillValue): áp dụng ngưỡng an toàn dựa trên
        # quan sát thực tế (ảnh "cdo infon" cho thấy Minimum không xuống tới -9000).
        gia_tri = np.where(gia_tri <= -9000, np.nan, gia_tri)
        gia_tri = np.where(np.abs(gia_tri) > 1e6, np.nan, gia_tri)

        lat_vals = np.asarray(ds.variables[lat_name][:], dtype="float64")
        lon_vals = np.asarray(ds.variables[lon_name][:], dtype="float64")

        thoi_gian_str = None
        if "time" in ds.variables:
            try:
                time_var = ds.variables["time"]
                cf_date = nc.num2date(
                    time_var[ts_index],
                    units=time_var.units,
                    calendar=getattr(time_var, "calendar", "standard"),
                )
                thoi_gian_str = cf_date.strftime("%Y-%m-%d")
            except Exception:
                thoi_gian_str = None

        return {
            "lon": lon_vals,
            "lat": lat_vals,
            "data": gia_tri,
            "thoi_gian_du_bao": thoi_gian_str,
            "loi": None,
        }
    finally:
        ds.close()


# ─── 5. Shapefile ranh giới (cache để không đọc lại mỗi lần) ───────────────
@st.cache_resource(show_spinner=False)
def doc_shapefile_xa():
    import geopandas as gpd
    return gpd.read_file(SHAPEFILE_XA)


@st.cache_resource(show_spinner=False)
def doc_ranh_gioi_tinh():
    """Lấy polygon ranh giới tỉnh Quảng Ninh từ shapefile 34 tỉnh, dùng để mask raster."""
    import geopandas as gpd
    gdf = gpd.read_file(SHAPEFILE_TINH)
    qn = gdf[gdf["ten_tinh"] == TEN_TINH]
    if qn.empty:
        return None
    return qn


# ─── 6. Tóm tắt giá trị trung bình theo từng xã (clip theo shapefile) ──────
def tinh_trung_binh_theo_xa(lon: np.ndarray, lat: np.ndarray, data: np.ndarray):
    """
    Trả về GeoDataFrame (bản sao của shapefile xã) có thêm cột 'gia_tri'
    = trung bình các điểm lưới rơi vào từng xã.
    """
    import shapely

    gdf = doc_shapefile_xa().copy()
    lon2d, lat2d = np.meshgrid(lon, lat)
    valid = ~np.isnan(data)

    pts_lon = lon2d[valid]
    pts_lat = lat2d[valid]
    pts_val = data[valid]

    ket_qua = []
    for geom in gdf.geometry:
        if pts_lon.size == 0:
            ket_qua.append(np.nan)
            continue
        trong_xa = shapely.contains_xy(geom, pts_lon, pts_lat)
        if trong_xa.sum() == 0:
            ket_qua.append(np.nan)
        else:
            ket_qua.append(float(np.mean(pts_val[trong_xa])))

    gdf["gia_tri"] = ket_qua
    return gdf


def mask_raster_theo_tinh(lon: np.ndarray, lat: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Trả về bản sao của `data` với các điểm nằm ngoài ranh giới tỉnh Quảng Ninh -> NaN."""
    import shapely

    qn = doc_ranh_gioi_tinh()
    if qn is None:
        return data  # không có ranh giới tỉnh -> trả nguyên bản, không mask

    geom = qn.union_all() if hasattr(qn, "union_all") else qn.unary_union
    lon2d, lat2d = np.meshgrid(lon, lat)
    mask = shapely.contains_xy(geom, lon2d, lat2d)
    return np.where(mask, data, np.nan)


# ─── 7. Nội suy IDW (k-NN) + làm mịn Gaussian – để lưới hiển thị mịn hơn ───
# Cùng phương pháp với hàm idw_knn() trong app nội suy quan trắc (k-NN nghịch đảo
# khoảng cách qua cKDTree), áp dụng cho lưới mô hình chuẩn sai khí hậu mùa.
def _idw_knn(xi: np.ndarray, yi: np.ndarray, zi: np.ndarray, query_xy: np.ndarray,
             k: int = 12, power: float = 3.0, eps: float = 1e-12) -> np.ndarray:
    """Nội suy nghịch đảo khoảng cách (IDW) dựa trên k láng giềng gần nhất (k-NN)."""
    from scipy.spatial import cKDTree

    tree = cKDTree(np.column_stack([xi, yi]))
    dists, idxs = tree.query(query_xy, k=min(k, xi.size))
    if dists.ndim == 1:
        dists, idxs = dists[:, None], idxs[:, None]

    exact = dists <= eps
    out = np.empty(dists.shape[0], dtype=float)
    if np.any(exact):
        for r in np.where(exact.any(axis=1))[0]:
            out[r] = zi[idxs[r, np.where(exact[r])[0][0]]]
    rest = ~exact.any(axis=1)
    if np.any(rest):
        d, nn = dists[rest], idxs[rest]
        w = 1.0 / np.maximum(d, eps) ** power
        out[rest] = (w * zi[nn]).sum(axis=1) / w.sum(axis=1)
    return out


def noi_suy_idw_luoi_min(
    lon: np.ndarray,
    lat: np.ndarray,
    data: np.ndarray,
    grid_n: int = 400,
    k: int = 12,
    power: float = 3.0,
    sigma: float = 1.2,
) -> dict:
    """
    Nội suy dữ liệu raster gốc (lưới thô của mô hình) sang lưới mịn hơn bằng IDW (k-NN)
    rồi làm mịn thêm bằng Gaussian filter — giúp bản đồ hiển thị mượt, không bị "rỗ" theo
    từng ô lưới mô hình.

    Tham số:
        lon, lat : tọa độ 1D của lưới gốc (như trả về từ doc_du_lieu_raster)
        data     : mảng 2D (lat, lon) giá trị tương ứng, NaN = missing/ngoài vùng
        grid_n   : số điểm lưới mịn theo mỗi chiều (lưới đầu ra grid_n × grid_n)
        k        : số láng giềng gần nhất dùng trong nội suy IDW
        power    : hệ số mũ nghịch đảo khoảng cách (càng lớn, ảnh hưởng điểm gần
                   biên độ áp đảo điểm xa)
        sigma    : độ lệch chuẩn Gaussian dùng làm mịn thêm sau nội suy (0 = bỏ qua)

    Trả về dict {
        'lon': np.ndarray 1D (lưới mịn),
        'lat': np.ndarray 1D (lưới mịn),
        'data': np.ndarray 2D (lưới mịn) đã nội suy + làm mịn,
    }
    """
    from scipy.ndimage import gaussian_filter

    lon2d, lat2d = np.meshgrid(lon, lat)
    valid = ~np.isnan(data)

    xi = lon2d[valid]
    yi = lat2d[valid]
    zi = data[valid]

    if xi.size == 0:
        # Không có điểm hợp lệ nào -> trả về lưới mịn toàn NaN, tránh lỗi cKDTree với mảng rỗng
        lon_fine = np.linspace(lon.min(), lon.max(), grid_n)
        lat_fine = np.linspace(lat.min(), lat.max(), grid_n)
        return {
            "lon": lon_fine,
            "lat": lat_fine,
            "data": np.full((grid_n, grid_n), np.nan),
        }

    lon_fine = np.linspace(lon.min(), lon.max(), grid_n)
    lat_fine = np.linspace(lat.min(), lat.max(), grid_n)
    gx, gy = np.meshgrid(lon_fine, lat_fine)
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])

    gv = _idw_knn(xi, yi, zi, grid_xy, k=k, power=power).reshape(gx.shape)
    if sigma > 0:
        gv = gaussian_filter(gv, sigma=sigma)

    return {"lon": lon_fine, "lat": lat_fine, "data": gv}
