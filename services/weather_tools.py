"""
Weather Tools Module
版本: rev2.4.3
4 支 stateless handler，提供天氣查詢功能給 Gemini Function Calling
"""

import math
import os
import time
from typing import Optional

import requests

DEFAULT_TIMEOUT = 8.0
CWA_API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
TDX_AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
TDX_API_URL = "https://tdx.transportdata.tw/api/basic/v2"

# CWA 鄉鎮天氣預報 — 各縣市 Dataset ID 對照表
# 來源: https://opendata.cwa.gov.tw/dataset/F-D0047
CITY_DATASET_MAP = {
    "宜蘭縣": "F-D0047-003", "桃園市": "F-D0047-007", "新竹縣": "F-D0047-011",
    "苗栗縣": "F-D0047-015", "彰化縣": "F-D0047-019", "南投縣": "F-D0047-023",
    "雲林縣": "F-D0047-027", "嘉義縣": "F-D0047-031", "屏東縣": "F-D0047-035",
    "臺東縣": "F-D0047-039", "花蓮縣": "F-D0047-043", "澎湖縣": "F-D0047-047",
    "基隆市": "F-D0047-051", "新竹市": "F-D0047-055", "嘉義市": "F-D0047-059",
    "臺北市": "F-D0047-063", "高雄市": "F-D0047-067", "新北市": "F-D0047-071",
    "臺中市": "F-D0047-075", "臺南市": "F-D0047-079", "連江縣": "F-D0047-083",
    "金門縣": "F-D0047-087",
}

# 常見別名 → 正式縣市名（正體字「臺」）
_CITY_ALIASES = {
    "宜蘭": "宜蘭縣", "桃園": "桃園市", "新竹": "新竹縣",
    "苗栗": "苗栗縣", "彰化": "彰化縣", "南投": "南投縣",
    "雲林": "雲林縣", "嘉義": "嘉義縣", "屏東": "屏東縣",
    "臺東": "臺東縣", "台東": "臺東縣",
    "花蓮": "花蓮縣", "澎湖": "澎湖縣", "基隆": "基隆市",
    "新竹市": "新竹市", "嘉義市": "嘉義市",
    "臺北": "臺北市", "台北": "臺北市", "北市": "臺北市",
    "高雄": "高雄市", "高市": "高雄市",
    "新北": "新北市", "新北市": "新北市",
    "臺中": "臺中市", "台中": "臺中市", "中市": "臺中市",
    "臺南": "臺南市", "台南": "臺南市", "南市": "臺南市",
    "連江": "連江縣", "金門": "金門縣",
}


def _resolve_dataset_id(location: str) -> tuple[str, str]:
    """從 location 字串解析出 (正式縣市名, dataset_id)。

    支援完整名稱（宜蘭縣）、別名（宜蘭）、
    以及去除「縣」「市」後綴的模糊匹配。
    回傳 (resolved_name, dataset_id) 或 ("", "")。
    """
    # 1. 完全匹配
    if location in CITY_DATASET_MAP:
        return location, CITY_DATASET_MAP[location]
    # 2. 別名匹配
    if location in _CITY_ALIASES:
        full = _CITY_ALIASES[location]
        return full, CITY_DATASET_MAP[full]
    # 3. 去掉「縣」「市」後綴再匹配
    for suffix in ("縣", "市"):
        stripped = location.rstrip(suffix)
        if stripped in _CITY_ALIASES:
            full = _CITY_ALIASES[stripped]
            return full, CITY_DATASET_MAP[full]
    return "", ""

# 縣市對應表（用於從 GPS 推測縣市）
CITY_COORDS = {
    "Taipei": (25.0330, 121.5654),
    "NewTaipei": (25.0169, 121.4584),
    "Taoyuan": (24.9937, 121.3009),
    "Taichung": (24.1477, 120.6736),
    "Tainan": (22.9999, 120.2270),
    "Kaohsiung": (22.6273, 120.3014),
    "Hsinchu": (24.8138, 120.9724),
    "HsinchuCounty": (24.8387, 121.0177),
    "MiaoliCounty": (24.5657, 120.8210),
    "ChanghuaCounty": (24.0518, 120.5161),
    "NantouCounty": (23.9092, 120.6827),
    "YunlinCounty": (23.7094, 120.4314),
    "Chiayi": (23.4800, 120.4491),
    "ChiayiCounty": (23.4518, 120.2554),
    "PingtungCounty": (22.5519, 120.5488),
    "YilanCounty": (24.7596, 121.7593),
    "HualienCounty": (23.9750, 121.6081),
    "TaitungCounty": (22.7583, 121.1444),
    "PenghuCounty": (23.5612, 119.5792),
    "Keelung": (25.1283, 121.7419),
}

_city_cctv_cache: dict[str, list] = {}


def _guess_city(lat: float, lon: float) -> str:
    """根據座標推測最近的縣市"""
    min_dist = float('inf')
    closest = "Taipei"
    for city, (clat, clon) in CITY_COORDS.items():
        dist = _haversine(lat, lon, clat, clon)
        if dist < min_dist:
            min_dist = dist
            closest = city
    return closest


def _fetch_city_cctvs(city: str) -> list:
    """查詢單一縣市監視器（含快取）"""
    if city in _city_cctv_cache:
        return _city_cctv_cache[city]
    token = _get_tdx_token()
    if not token:
        return []
    try:
        resp = requests.get(
            f"{TDX_API_URL}/Road/Traffic/CCTV/City/{city}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"$top": 300, "$format": "JSON"},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code == 429:
            return []
        resp.raise_for_status()
        data = resp.json()
        cctvs = data.get("CCTVs", []) if isinstance(data, dict) else []
        _city_cctv_cache[city] = cctvs
        return cctvs
    except Exception:
        return []


_tdx_token: str = ""
_tdx_token_expiry: float = 0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_tdx_token() -> Optional[str]:
    global _tdx_token, _tdx_token_expiry
    if _tdx_token and time.time() < _tdx_token_expiry:
        return _tdx_token
    client_id = os.getenv("TDX_CLIENT_ID", "")
    client_secret = os.getenv("TDX_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None
    try:
        resp = requests.post(
            TDX_AUTH_URL,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _tdx_token = data["access_token"]
        _tdx_token_expiry = time.time() + data.get("expires_in", 86400) - 60
        return _tdx_token
    except Exception:
        return None


def get_rain_probability(location: str, start_date: str = None, end_date: str = None):
    """查詢指定縣市的12小時降雨機率預報（最多7日）。

    Args:
        location: 縣市名稱（支援正體、別名、簡稱，如「宜蘭」「宜蘭縣」「臺北市」）
        start_date: 起始日期 YYYY-MM-DD（選填）
        end_date: 結束日期 YYYY-MM-DD（選填）
    """
    api_key = os.getenv("CWA_API_KEY", "")
    if not api_key:
        return {"error": "CWA_API_KEY not set"}
    resolved_name, dataset_id = _resolve_dataset_id(location)
    if not dataset_id:
        return {"error": f"無法識別的縣市名稱: {location}。請使用正體中文全名，如「宜蘭縣」「臺北市」。"}
    try:
        resp = requests.get(
            f"{CWA_API_URL}/{dataset_id}",
            params={"Authorization": api_key, "format": "JSON", "locationName": resolved_name, "elementName": "12小時降雨機率"},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code == 401:
            return {"error": "CWA API Key invalid"}
        resp.raise_for_status()
        data = resp.json()
        locations = data.get("records", {}).get("Locations", [])
        if not locations:
            return {"error": f"Location not found: {resolved_name}"}
        weather_elements = locations[0].get("Location", [{}])[0].get("WeatherElement", [])
        pop_elements = [el for el in weather_elements if el.get("ElementName") == "12小時降雨機率"]
        if not pop_elements:
            return {"error": "No rain probability data"}
        results = []
        from datetime import datetime
        for entry in pop_elements[0].get("Time", []):
            time_str = entry.get("StartTime") or entry.get("DataTime")
            dt = datetime.fromisoformat(time_str)
            date_str = dt.strftime("%Y-%m-%d")
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue
            val_dict = entry.get("ElementValue", [{}])[0]
            val = list(val_dict.values())[0] if val_dict else "0"
            results.append({"date": date_str, "time": dt.strftime("%H:%M"), "pop": val})
        return {"location": resolved_name, "data": results}
    except Exception as e:
        return {"error": str(e)}


def get_gps_weather(lat: float, lon: float, station_count: int = 3):
    api_key = os.getenv("CWA_API_KEY", "")
    if not api_key:
        return {"error": "CWA_API_KEY not set"}
    try:
        resp = requests.get(
            f"{CWA_API_URL}/O-A0003-001",
            params={"Authorization": api_key, "format": "JSON", "lat": lat, "lon": lon},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        stations = data.get("records", {}).get("Station", [])
        if not stations:
            return {"error": "No station data"}
        def get_wgs84(s):
            for c in s.get("GeoInfo", {}).get("Coordinates", []):
                if c.get("CoordinateName") == "WGS84":
                    try:
                        return (float(c["StationLatitude"]), float(c["StationLongitude"]))
                    except (KeyError, ValueError):
                        return None
            return None
        def is_valid(v):
            if not v or v.strip() == "":
                return False
            try:
                return abs(float(v) + 99) > 0.001
            except ValueError:
                return False
        scored = []
        for s in stations:
            wgs = get_wgs84(s)
            if wgs:
                scored.append({"station": s, "dist": _haversine(lat, lon, wgs[0], wgs[1])})
        scored.sort(key=lambda x: x["dist"])
        results = []
        for item in scored[:station_count]:
            s = item["station"]
            we = s.get("WeatherElement", {})
            results.append({
                "station": s.get("StationName", ""),
                "distance_km": round(item["dist"], 2),
                "temp": float(we["AirTemperature"]) if is_valid(we.get("AirTemperature")) else None,
                "humidity": float(we["RelativeHumidity"]) if is_valid(we.get("RelativeHumidity")) else None,
                "weather": we.get("Weather", ""),
                "rain": float(we.get("Now", {}).get("Precipitation", 0)) if is_valid(we.get("Now", {}).get("Precipitation")) else 0,
            })
        return results
    except Exception as e:
        return {"error": str(e)}


def get_nearby_cctv(lat: float, lon: float, radius_km: float = 2.0):
    city = _guess_city(lat, lon)
    cctvs = _fetch_city_cctvs(city)
    if not cctvs:
        return {"error": f"No CCTV data for {city}"}
    results = []
    for c in cctvs:
        clat = c.get("PositionLat")
        clon = c.get("PositionLon")
        if clat and clon:
            dist = _haversine(lat, lon, clat, clon)
            if dist <= radius_km:
                results.append({
                    "cctv_id": c.get("CCTVID", ""),
                    "road_name": c.get("RoadName", ""),
                    "lat": clat,
                    "lon": clon,
                    "distance_km": round(dist, 2),
                    "available": bool(c.get("CCTVUrl")),
                    "image_url": c.get("CCTVUrl", ""),
                })
    results.sort(key=lambda x: x["distance_km"])
    return results[:10]


ROUTES = {
    "台3線": [
        {"name": "台北", "gps": "25.0330,121.5654"},
        {"name": "桃園", "gps": "24.9937,121.3009"},
        {"name": "新竹", "gps": "24.8138,120.9724"},
    ],
    "台9線": [
        {"name": "台北", "gps": "25.0330,121.5654"},
        {"name": "宜蘭", "gps": "24.7596,121.7593"},
        {"name": "花蓮", "gps": "23.9750,121.6081"},
    ],
}


def plan_route_weather(route_name: str = None, waypoints: list = None):
    if waypoints:
        points = waypoints
        route_name = "自訂路線"
    elif route_name and route_name in ROUTES:
        points = ROUTES[route_name]
    else:
        return {"error": f"Route not found: {route_name}"}
    results = []
    cctv_count = 0
    for p in points:
        parts = p["gps"].split(",")
        plat, plon = float(parts[0]), float(parts[1])
        weather = get_gps_weather(plat, plon, station_count=1)
        cctv = get_nearby_cctv(plat, plon, radius_km=2.0)
        has_cctv = isinstance(cctv, list) and len(cctv) > 0
        if has_cctv:
            cctv_count += 1
        results.append({
            "name": p["name"],
            "weather": weather if isinstance(weather, list) else {"error": weather.get("error", "unknown")},
            "cctv_available": has_cctv,
        })
    coverage = f"{cctv_count}/{len(points)} ({round(cctv_count / len(points) * 100)}%)" if points else "0/0 (0%)"
    return {"route_name": route_name, "waypoints": results, "cctv_coverage_rate": coverage}
