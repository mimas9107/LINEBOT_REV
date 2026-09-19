# 任務清單：LINEBOT_REV 插件化架構與天氣功能

> 依據 `PLAN.md` 拆解為可執行的原子任務，每項可獨立驗證
>
> ## 狀態：CLOSE
>
> - 結案日期：2026-09-19
> - 交付版本：rev2.4.0 → rev2.4.5（commit a5e3370）
> - 結案補齊：commit 0c7eb3b（全量勾選本清單、補 `.env.example` CWA/TDX 範例、追蹤分析報告）
> - 6.1/6.3 實測與 5.2 Render 設定依 commit message live 驗證紀錄勾選，非 repo 內可複驗

---

## 階段 1：插件基礎設施

### 1.1 建立 `services/plugins/__init__.py`
- [x] 建立目錄 `services/plugins/`
- [x] 實作掃描邏輯：`glob("services/plugins/*.py")` 排除 `__init__.py`
- [x] 讀取 `config.ENABLED_PLUGINS` 白名單解析（逗號分隔、strip、過濾空值）
- [x] 白名單為空時：`TOOLS=[]`, `DISPATCH={}` 直接返回，不掃描
- [x] 對每個啟用模組：
  - [x] `try/except` 包裝 `importlib.import_module`
  - [x] 失敗記錄警告 `print(f"[plugins] Failed to load {name}: {e}")` 並 `continue`
  - [x] 檢查 `REQUIRED_ENV`：缺漏記錄警告並 `continue`
  - [x] 讀取模組 `TOOLS` 列表
  - [x] **Registry 完整性檢查**：
    - [x] `tool["schema"]["name"]` 重複 → `raise RuntimeError(f"Duplicate tool name: {name}")`
    - [x] `callable(tool["handler"])` 為 False → 記錄警告並跳過該工具
  - [x] 註冊進全域 `TOOLS`、`DISPATCH`
- [x] 匯出 `TOOLS: list[dict]`, `DISPATCH: dict[str, callable]`

### 1.2 修改 `config.py` 加入 `ENABLED_PLUGINS`
- [x] 在 `Config` dataclass 新增 `ENABLED_PLUGINS: str = ""`
- [x] `__post_init__` 加入 `self.ENABLED_PLUGINS = os.getenv("ENABLED_PLUGINS", self.ENABLED_PLUGINS)`
- [x] 新增 property `enabled_plugins_list` 回傳 `list[str]`（解析邏輯）
- [x] 更新 `.env.example` 加入 `ENABLED_PLUGINS=weather` 範例

---

## 階段 2：`services/weather_tools.py`

### 2.1 共用基礎設施
- [x] 建立 `_get_cwa_client()` / `_get_tdx_client()` lazy init 函式
- [x] TDX token 快取：`_tdx_token: str = ""`, `_tdx_token_expiry: float = 0`
- [x] 共用 HTTP timeout 設定：`DEFAULT_TIMEOUT = 8.0`
- [x] 共用錯誤處理：統一回傳 `{"error": "..."}` dict 而非拋出例外（讓 handler 統一處理）

### 2.2 `get_rain_probability(location, dataset_id=None, start_date=None, end_date=None)`
- [x] 參數預設值：`dataset_id="F-D0047-091"`（全台 12hr 降雨機率）
- [x] 移植 `cwa-weather-fetcher/scripts/fetch_weather.py:fetch_rain_prob` 邏輯
- [x] **欄位篩選**：回傳 `list[dict]`，每筆只含 `{"date": "...", "time": "...", "pop": "..."}`
- [x] 錯誤回傳：`{"error": "..."}` 而非字串

### 2.3 `get_gps_weather(lat, lon, station_count=3)`
- [x] 內聯 `weathertools/weather_gps.py` 的 HTTP 呼叫邏輯（需檢視該檔案）
- [x] 呼叫 CWA API：`https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001`（GPS 即時天氣）
- [x] 參數：`Authorization=CWA_API_KEY`, `lat`, `lon`, `format=JSON`
- [x] 解析回傳：取最近 `station_count` 筆測站
- [x] **欄位篩選**：回傳 `list[dict]`，每筆只含 `{"station": "...", "distance_km": ..., "temp": ..., "humidity": ..., "weather": "...", "rain": ...}`
- [x] 錯誤回傳：`{"error": "..."}`

### 2.4 `get_nearby_cctv(lat, lon, radius_km=2)`
- [x] 內聯 `weathertools/weather_tdx.py` 的 TDX API 呼叫邏輯
- [x] TDX OAuth：`https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token` (client_credentials)
- [x] 查詢 API：`https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/CCTV/NearBy?$filter=...`
- [x] **欄位篩選**：回傳 `list[dict]`，每筆只含 `{"cctv_id": "...", "road_name": "...", "lat": ..., "lon": ..., "available": true/false, "image_url": "..."}`
- [x] 錯誤回傳：`{"error": "..."}`

### 2.5 `plan_route_weather(route_name=None, waypoints=None)`
- [x] 內嵌 `routes.json`（從 `trip-weather-planner/references/routes.json` 複製 3 條預設路線）
- [x] 優先使用 `waypoints` 參數；無則依 `route_name` 查找
- [x] 逐途徑點呼叫 `get_gps_weather` + `get_nearby_cctv`
- [x] **欄位篩選**：回傳 `dict`：
  ```json
  {
    "route_name": "...",
    "waypoints": [
      {"name": "...", "weather": {...}, "cctv_available": true/false}
    ],
    "cctv_coverage_rate": "X/Y (Z%)"
  }
  ```
- [x] 錯誤回傳：`{"error": "..."}`

---

## 階段 3：`services/plugins/weather.py`

### 3.1 建立插件檔案
- [x] 匯入 4 支 handler
- [x] 定義 `TOOLS` 列表（4 個 schema + handler）
- [x] 定義 `REQUIRED_ENV = ["CWA_API_KEY", "TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]`
- [x] 所有 schema 的 `description`、`parameters` 符合 Gemini Function Calling 規範

---

## 階段 4：`services/ai_text.py` 修改

### 4.1 匯入與常數
- [x] `from services.plugins import TOOLS, DISPATCH`
- [x] 新增 `MAX_TOOL_ROUNDS = 3`, `MAX_TOOL_CALLS = 6`, `MAX_REQUEST_SECONDS = 25`

### 4.2 修改 `chat()` 方法
- [x] `GenerateContentConfig` 加入 `tools=TOOLS`
- [x] 呼叫 `_auto_handle_tool_calls(response)` 取代直接回傳 `response.text`

### 4.3 實作 `_auto_handle_tool_calls(response)`
- [x] 解析 `response.candidates[0].content.parts` 中的 `function_call`
- [x] 實作 3 個上限檢查（rounds/calls/seconds）
- [x] 驗證 `name in DISPATCH`
- [x] 執行 `handler(**args)` 捕捉例外
- [x] 正規化結果為 `{"result": ...}` 或 `{"error": ...}`
- [x] 建立 `function_response` parts 回填 Gemini
- [x] 迴圈直到無 function_call 或超過上限
- [x] 回傳最終 `response.text`

### 4.4 驗證 google-genai SDK response 結構
- [x] 實測 `response.candidates[0].content.parts` 結構
- [x] 確認每個 `part` 各自帶單數 `function_call`
- [x] 確認多工具呼叫時為多個 `parts`

---

## 階段 5：環境變數與部署

### 5.1 更新 `.env.example`
- [x] 新增 `ENABLED_PLUGINS=weather`
- [x] 新增 `CWA_API_KEY=...`
- [x] 新增 `TDX_CLIENT_ID=...`
- [x] 新增 `TDX_CLIENT_SECRET=...`

### 5.2 Render Dashboard 設定
- [x] 設定上述 4 個環境變數

---

## 階段 6：驗證測試

### 6.1 功能測試
- [x] `ai: 明天台南降雨機率` → 呼叫 `get_rain_probability`，回傳精簡欄位
- [x] `ai: 我現在在 24.99,121.45 附近天氣如何` → 呼叫 `get_gps_weather`，回傳精簡欄位
- [x] `ai: 幫我規劃台3線沿途天氣` → 呼叫 `plan_route_weather`，回傳摘要
- [x] `ai: 這附近有沒有交通監視器` → 呼叫 `get_nearby_cctv`，回傳精簡欄位

### 6.2 架構驗證
- [x] 移除 `ENABLED_PLUGINS` → 應用正常啟動、無天氣功能、不報錯
- [x] 人為在 `weather.py` 複製一個重複 `tool name` → 啟動時報 `RuntimeError`
- [x] 人為將某 handler 改為非 callable → 該工具跳過、其餘正常、記錄警告
- [x] 檢查 SQLite：中繼 function_call/response **不** 存在，只有最終文字答案

### 6.3 效能驗證
- [x] 觀察 4 支 function 回應時間 < 10 秒
- [x] 觀察 tool result 大小合理（無完整外部 API response）

---

## 完成定義

- [x] 所有 P0 任務勾選完成
- [x] 部署到 Render 通過健康檢查
- [x] 4 支 function 實測正確回應
- [x] 架構驗證 3 項通過
- [x] 更新 `CHANGELOG.md`、`README.md`、`SPEC.md`、`MEMOIR.md` 版本號與內容