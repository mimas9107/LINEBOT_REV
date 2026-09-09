# 實作計畫：LINEBOT_REV 插件化架構與天氣功能

> 依據 `CROSS_PROJECT_ANALYSIS_20260909a.md` 定版規格製作

---

## 專案現況

- **架構**：Flask + google-genai SDK + SQLite + LINE Bot SDK v3
- **核心服務**：`services/ai_text.py` (Gemini 對話)、`handlers/line_handler.py` (Webhook 處理)
- **部署**：Render (gunicorn, 300s timeout, 單 worker)
- **現有環境變數**：見 `.env.example`，尚無 `ENABLED_PLUGINS`、CWA/TDX 憑證

---

## 實作步驟總覽

| 階段 | 項目 | 檔案 | 優先級 |
|------|------|------|--------|
| 1 | 插件基礎設施 | `services/plugins/__init__.py`, `config.py` | P0 |
| 2 | Stateless handler 模組 | `services/weather_tools.py` | P0 |
| 3 | 天氣插件檔案 | `services/plugins/weather.py` | P0 |
| 4 | AI 服務接入插件系統 | `services/ai_text.py` | P0 |
| 5 | 環境變數設定 | Render Dashboard / `.env.example` | P0 |
| 6 | 部署驗證 | 手動測試 4 支 function | P0 |

---

## 詳細規格

### 階段 1：插件基礎設施

#### `services/plugins/__init__.py` (新建)
- 掃描 `services/plugins/` 目錄下所有 `.py` 檔案（排除 `__init__.py`）
- 讀取 `config.ENABLED_PLUGINS` 白名單（逗號分隔，**必填，空值不啟用任何插件**）
- 對白名單內每個模組：
  - `try/except` 包裝 import，失敗記錄警告並跳過（不拖垮全站）
  - 檢查 `REQUIRED_ENV` 環境變數是否齊全，缺漏則跳過該插件
  - 讀取模組的 `TOOLS` 列表，每個項目包含 `schema`、`handler`、`policy`(可選)
  - **Registry 完整性檢查（新增）**：
    - `tool name` 重複 → **startup error**，直接 raise，阻止啟動
    - `handler` 非 callable → 視為該插件載入失敗，記錄警告並跳過
  - 註冊進全域 `TOOLS: list[dict]`、`DISPATCH: dict[str, callable]`
- 匯出公開符號：`TOOLS`、`DISPATCH`

#### `config.py` (修改)
- 新增 `ENABLED_PLUGINS: str = ""` 屬性
- `__post_init__` 讀取環境變數
- 解析邏輯：逗號分隔、strip、過濾空字串 → `list[str]`
- **不再支援「空值 = 全部啟用」**，空字串或未設定 = 啟用 0 個插件

### 階段 2：`services/weather_tools.py` (新建)

4 支 stateless handler，**每支函式回傳前必須篩選欄位，不可原樣回傳外部 API response**。

| 函式 | 參數 | 來源 | 關鍵實作重點 |
|------|------|------|--------------|
| `get_rain_probability` | `location: str, dataset_id?: str, start_date?: str, end_date?: str` | `cwa-weather-fetcher.fetch_rain_prob` | 直接移植，參數名標準化，**回傳前只留 `date`、`time`、`pop`** |
| `get_gps_weather` | `lat: float, lon: float, station_count?: int` | `weathertools/weather_gps.py` | 內聯 HTTP 呼叫，**移除 subprocess**，回傳前只留 `station`、`distance`、`temp`、`humidity`、`weather`、`rain` |
| `plan_route_weather` | `route_name?: str, waypoints?: list[dict]` | `trip-weather-planner` 編排邏輯 | 載入 `routes.json`（專案內嵌），呼叫上述兩函式，**回傳前只留途徑點名稱、天氣摘要、CCTV 覆蓋率** |
| `get_nearby_cctv` | `lat: float, lon: float, radius_km?: float` | `weathertools/weather_tdx.py` | 內聯 TDX API（OAuth token + 查詢），**回傳前只留 `cctv_id`、`road_name`、`lat`、`lon`、`available` 等 Gemini 需要的欄位** |

**共同規範**：
- 所有 `requests`/`httpx` 呼叫 **timeout = 5–8 秒**（明確設定）
- 任何 client/session 物件 **lazy init**（模組頂層不初始化，用 `_get_client()` 模式）
- TDX token 允許 module-level 唯讀快取（token + 過期時間），不共享可變狀態
- 回傳型別：JSON serializable（list/dict/str/int/float/bool/None）

### 階段 3：`services/plugins/weather.py` (新建)

```python
from services.weather_tools import (
    get_rain_probability,
    get_gps_weather,
    plan_route_weather,
    get_nearby_cctv,
)

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

REQUIRED_ENV = ["CWA_API_KEY", "TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]
```

### 階段 4：`services/ai_text.py` 修改

#### 匯入變更
```python
from services.plugins import TOOLS, DISPATCH
```

#### 新增常數
```python
MAX_TOOL_ROUNDS = 3        # Gemini 來回輪數
MAX_TOOL_CALLS = 6         # 單次 request 總 tool call 數（一輪可能有多個 parallel call）
MAX_REQUEST_SECONDS = 25   # 單次 request 硬性時間上限
```

#### `chat()` 方法
- 建立 `GenerateContentConfig` 時加入 `tools=TOOLS`
- 呼叫 `_auto_handle_tool_calls(response)` 處理迴圈

#### `_auto_handle_tool_calls(response)` 實作邏輯（單一函式，內部依 pipeline 順序）

```python
def _auto_handle_tool_calls(self, response):
    rounds = 0
    total_calls = 0
    start_time = time.monotonic()
    
    while True:
        # 1. Parse: 從 response.candidates[0].content.parts 提取 function_call
        #    注意：每個 part 各自帶單數 function_call，多工具 = 多 parts
        calls = self._parse_function_calls(response)
        if not calls:
            return response.text  # 最終文字答案
        
        # 2. 檢查上限
        rounds += 1
        if rounds > MAX_TOOL_ROUNDS:
            break
        total_calls += len(calls)
        if total_calls > MAX_TOOL_CALLS:
            break
        if time.monotonic() - start_time > MAX_REQUEST_SECONDS:
            break
        
        # 3. Validate + Execute: 逐個呼叫
        function_responses = []
        for call in calls:
            name = call.name
            args = dict(call.args) if call.args else {}
            
            if name not in DISPATCH:
                function_responses.append(types.Part.from_function_response(
                    name=name,
                    response={"error": f"Unknown tool: {name}"}
                ))
                continue
            
            handler = DISPATCH[name]
            try:
                result = handler(**args)
                # 4. Normalize: 確保 JSON serializable
                function_responses.append(types.Part.from_function_response(
                    name=name,
                    response={"result": result}
                ))
            except Exception as e:
                function_responses.append(types.Part.from_function_response(
                    name=name,
                    response={"error": str(e)}
                ))
        
        # 5. 回填 Gemini
        response = self._get_client().models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[types.Content(role="user", parts=function_responses)],
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                tools=TOOLS,
            )
        )
    
    # 超過上限時回傳提示
    return "工具呼叫超過上限，請簡化問題或稍後再試。"
```

**關鍵點**：
- 中繼 `function_call` / `function_response` **只存在記憶體 context**，不寫入 SQLite
- 只有迴圈結束後的最終 `response.text` 才會觸發既有的 `chat_history` 寫入流程（由 `handlers/line_handler.py` 處理）
- 動工前必須對照 `google-genai` SDK 實際版本驗證 `response.candidates[0].content.parts` 結構

### 階段 5：環境變數

#### `.env.example` 新增
```
# Plugin system
ENABLED_PLUGINS=weather

# Weather APIs
CWA_API_KEY=your_cwa_api_key_here
TDX_CLIENT_ID=your_tdx_client_id_here
TDX_CLIENT_SECRET=your_tdx_client_secret_here
```

#### Render Dashboard 設定
- 同上 4 個環境變數

### 階段 6：部署驗證

| 測試指令 | 預期呼叫 | 驗證重點 |
|----------|----------|----------|
| `ai: 明天台南降雨機率` | `get_rain_probability` | 回傳欄位已篩選（只有 date/time/pop） |
| `ai: 我現在在 24.99,121.45 附近天氣如何` | `get_gps_weather` | 回傳欄位已篩選，無完整 CWA JSON |
| `ai: 幫我規劃台3線沿途天氣` | `plan_route_weather` | 回傳途徑點摘要，無原始 API response |
| `ai: 這附近有沒有交通監視器` | `get_nearby_cctv` | 回傳精簡 CCTV 資訊，無完整 TDX metadata |

**額外驗證**：
- 移除 `ENABLED_PLUGINS` 或設為空 → 插件不載入、不拖垮全站
- 人為製造重複 `tool name` → 啟動時報錯（startup error）
- 人為製造非 callable handler → 該插件跳過、其餘正常

---

## 風險與對策（摘自分析報告）

| 風險 | 等級 | 對策 |
|------|------|------|
| A: import 容錯 | P0 | try/except + lazy init + REQUIRED_ENV 檢查 |
| C: timeout 放大 | P0 | 5-8s timeout + 三個獨立上限 |
| H: tool result 未篩選 | P0 | 每支 handler return 前欄位篩選 |
| D: TDX token 快取 | P1 | module-level 唯讀快取（token+expiry） |
| F: SDK 結構驗證 | P1 | 動工前實測 google-genai 版本 response 結構 |
| B: 中繼資料不落 DB | P1 | 僅最終文字答案寫入 chat_history |

---

## 後續擴充（不擋本週）

- 下週：`services/plugins/tra.py`（臺鐵 3 支 function）
- 再下週：`services/plugins/hackmd.py`（HackMD 5 支 function + policy 授權層）
- HackMD 上線前必解：lazy init、async handler 支援、policy 實際生效