"""
Weather Plugin
版本: rev2.4.1
天氣查詢功能模組，提供 Gemini Function Calling 使用
"""

from services.weather_tools import (
    get_rain_probability,
    get_gps_weather,
    plan_route_weather,
    get_nearby_cctv,
)

REQUIRED_ENV = ["CWA_API_KEY", "TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]

TOOLS = [
    {
        "schema": {
            "name": "get_rain_probability",
            "description": "獲取指定縣市的 12 小時降雨機率預報",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "縣市名稱（正體字，如：臺南市）"},
                    "dataset_id": {"type": "string", "description": "CWA 資料集 ID（選填，預設 F-D0047-091）"},
                    "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD（選填）"},
                    "end_date": {"type": "string", "description": "結束日期 YYYY-MM-DD（選填）"},
                },
                "required": ["location"],
            },
        },
        "handler": get_rain_probability,
    },
    {
        "schema": {
            "name": "get_gps_weather",
            "description": "查詢指定 GPS 座標附近測站的即時天氣",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "緯度"},
                    "lon": {"type": "number", "description": "經度"},
                    "station_count": {"type": "integer", "description": "回傳測站數量（預設 3）"},
                },
                "required": ["lat", "lon"],
            },
        },
        "handler": get_gps_weather,
    },
    {
        "schema": {
            "name": "plan_route_weather",
            "description": "規劃路線沿途天氣與 CCTV 覆蓋",
            "parameters": {
                "type": "object",
                "properties": {
                    "route_name": {"type": "string", "description": "預設路線名稱（如：台3線）"},
                    "waypoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "gps": {"type": "string"},
                            },
                            "required": ["name", "gps"],
                        },
                        "description": "自訂途徑點（選填，優先於 route_name）",
                    },
                },
            },
        },
        "handler": plan_route_weather,
    },
    {
        "schema": {
            "name": "get_nearby_cctv",
            "description": "查詢指定座標附近的交通監視器",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "緯度"},
                    "lon": {"type": "number", "description": "經度"},
                    "radius_km": {"type": "number", "description": "搜尋半徑公里數（預設 2）"},
                },
                "required": ["lat", "lon"],
            },
        },
        "handler": get_nearby_cctv,
    },
]
