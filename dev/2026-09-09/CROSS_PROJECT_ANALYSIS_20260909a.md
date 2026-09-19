# 跨專案分析報告（定版）：LINEBOT_REV 插件化架構與天氣功能實作規劃

> 本文件為 `CROSS_PROJECT_ANALYSIS_20260909.md` 的修訂版。修訂依據：外部團隊對原報告的評審意見，逐點裁決後產生。裁決原則見第零部份。本版可直接作為 coding agent（GLM-5.3 規劃 → big-pickle 執行）的施工規格。

---

## 第零部份：修訂裁決總覽

外部評審共提出 16 點意見。逐點裁決如下，裁決狀態分四種：

- **採納**：直接寫入本版 contract
- **採納（輕量版）**：方向對，但依目前規模（單人維護、私有 LINE bot、本週僅出 4 支唯讀天氣 function）簡化實作方式
- **記錄不擋路**：方向對，但屬於未來階段（tra/hackmd 上線時）才需要解決，先佔位不動工
- **維持原判**：評審意見不成立或成本效益不划算，保留原報告設計

| # | 評審意見 | 裁決 | 理由 |
|---|----------|------|------|
| 1 | `REQUIRED_ENV` 時序矛盾，需拆 metadata/implementation 兩階段 import | **採納（輕量版）** | 原報告風險 A 已分開處理「import 例外」與「env 缺漏」，評審點出的真正漏洞是報告自己的 HackMD 範例（附錄，`_client = HackMDClient(...)`）違反了風險 A 自訂的 lazy init 規則，不需要拆兩階段架構，貫徹既有規則即可 |
| 2 | 「純函式」應改稱「stateless handler」 | **採納** | 用詞修正，零成本 |
| 3 | Authorization 應是 registry 層 policy，不是 HackMD 專屬邏輯 | **採納（輕量版）** | `TOOLS` schema 保留 `policy` 佔位欄位，本週不填值；完整分級留到 HackMD 上線前 |
| 4 | Registry 需 runtime validation（重複 tool name、handler 非 callable） | **採納** | 成本低，防呆效益高 |
| 5 | Tool-calling loop 應拆成完整 Executor pipeline，而非 `DISPATCH[name](**args)` | **採納（輕量版）** | 本週用單一函式實作，但內部步驟依評審建議的 pipeline 順序寫，為未來拆分預留邊界 |
| 6 | Tool result 缺少 size/normalization 限制 | **採納，拉高為 P0** | 原報告完全沒提到的真實缺口，直接影響單 worker + 300 秒 timeout 架構的穩定性 |
| 7 | `MAX_TOOL_ROUNDS` 應拆成 rounds/calls/seconds 三個上限 | **採納** | 成本低 |
| 8 | `ENABLED_PLUGINS` 預設全開應改為明確白名單 | **採納** | 評審把風險講得偏誇張（單人私有 bot 不等於多租戶 SaaS），但改法成本幾乎是零，值得直接採納 |
| 9 | 新增 plugin 應含單元測試 + registry validation，不只是「新增檔案」 | **採納（輕量版）** | 併入 #4 的 registry validation，不另立完整測試流程 |
| 10 | weather 邏輯內聯化會與原始 `weathertools` 專案分岔 | **記錄不擋路** | 原報告已列為 P2，維持原判斷 |
| 11 | HackMD asyncio 包裝法、sync/async handler 都要支援 | **記錄不擋路** | hackmd.py 開工時才需要決定，方向記錄：用 `inspect.iscoroutinefunction` 判斷是否 `await`，不強制 `asyncio.run()` 包裝所有 handler |
| 12 | 應畫出 Gemini → Executor → Registry → plugin 的分層圖 | **採納** | 文件清晰度改善，列入本版第一部份 |
| 13 | 肯定 HackMD 部分沒有重新發明 client | 無需裁決 | 純肯定意見 |
| 14 | 重排 P0/P1 優先序 | **部分採納** | 見第零部份下方「本週最終 P0」 |
| 15 | `MAX_TOOL_ROUNDS=3` 不等於「最多執行 3 個 tools」 | **併入 #7** | — |
| 16 | 定版前要先把三句概念換掉（pure function / REQUIRED_ENV 時序 / DISPATCH 直接呼叫） | **併入 #1 #2 #5** | — |

### 本週最終 P0（僅擋天氣功能，不含 tra/hackmd）

1. `services/plugins/__init__.py`：import try/except + REQUIRED_ENV 檢查 + **重複 tool name / handler 非 callable 檢查**（新增）
2. `services/weather_tools.py`：4 支函式 timeout 5–8 秒 + **回傳前欄位篩選，不可原樣回傳外部 API response**（新增，前身報告未提及）
3. `ai_text.py`：`_auto_handle_tool_calls()` 拆分 `MAX_TOOL_ROUNDS` / `MAX_TOOL_CALLS` / `MAX_REQUEST_SECONDS`（原本只有 rounds）
4. `config.py`：`ENABLED_PLUGINS` 改為必填白名單，取消「空值 = 全部啟用」的預設行為
5. 中繼 function_call/function_response 不落 SQLite，只有最終文字答案寫入 `chat_history`（維持原判）
6. 動工前對照 google-genai SDK 實際版本驗證 `response.candidates[0].content.parts` 結構（維持原判，每個 part 各自帶單數 `function_call`）

---

## 第一部份：架構論述 —— 插件系統設計（定版）

### 核心洞察

**Gemini Function Calling 本身就是插件介面**。架構的任務只有一個：**讓「新增一個 function」變成唯一的開發動作**——但這個「唯一動作」必須通過一組不可歧義的 contract，而不是單純「新增檔案」。

### 分層架構圖

```
                 ┌────────────────────┐
                 │       Gemini       │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │  Tool Call Handler  │  ← ai_text.py：_auto_handle_tool_calls()
                 │                    │     本週：單一函式，內部依序：
                 │ - parse call       │     parse → validate name in DISPATCH →
                 │ - validate name    │     execute → normalize → 回填 Gemini
                 │ - execute          │     （為未來拆成獨立 Executor 類別預留邊界，
                 │ - normalize result │      本週不強行拆分）
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │      Registry      │  ← services/plugins/__init__.py
                 │                    │
                 │ TOOLS              │
                 │ DISPATCH           │
                 │ (policy: 佔位，本週不填) │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │    weather.py      │  ← 本週唯一新增檔案
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │  weather_tools.py  │  ← stateless handler，回傳前做欄位篩選
                 └────────────────────┘
```

`chat_history`（SQLite）只接在 Tool Call Handler 的最終輸出端，不接在 Registry 或 plugin 層：

```
User message → Gemini → (Tool Call Handler 迴圈，中繼結果只存記憶體) → 最終文字答案 → SQLite
```

### 近零摩擦的定義（維持）

| 週次 | 新增功能 | 開發者要做的事 |
|------|----------|----------------|
| 這週 | 天氣 4 支 function | 寫 1 個檔案、通過 registry validation、部署 |
| 下週 | 臺鐵 3 支 function | 同上 |
| 再下週 | HackMD 3 支 function | 同上 + 授權層 |

**零摩擦 = 不改 core、不改 config 結構、不動 Tool Call Handler、不動部署流程；但每次新增仍需通過 registry validation（重複名稱、handler callable 檢查），這不是額外摩擦，是啟動時自動跑的防呆。**

---

### 架構介面契約（定版）

#### 1. 單一註冊點

```
services/
└── plugins/
    ├── __init__.py          # 唯一掃描入口，永遠不動
    ├── weather.py           # 這週新增
    ├── tra.py               # 下週新增
    └── hackmd.py            # 再下週新增
```

`__init__.py` 職責：掃描 → 依 `ENABLED_PLUGINS` 白名單過濾 → try/except 隔離單一插件失敗 → 檢查 `REQUIRED_ENV` → **檢查 tool name 是否重複、handler 是否為 callable**（本版新增）→ 註冊進 `TOOLS`/`DISPATCH`。

任何一項 registry 完整性檢查失敗（重複 tool name）視為 **startup error**，與單一插件壞掉（跳過該插件、其餘照常）分開處理，不可混為一談。

#### 2. 插件檔案標準介面

```python
# services/plugins/weather.py
from services.weather_tools import get_rain_probability, ...

TOOLS = [
    {
        "schema": {
            "name": "get_rain_probability",
            "description": "獲取指定縣市的 12 小時降雨機率預報",
            "parameters": {...}
        },
        "handler": get_rain_probability,
        # "policy": {...}  # 佔位欄位，本週不填，預設視為唯讀
    },
]

REQUIRED_ENV = ["CWA_API_KEY", "TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]
```

**關鍵點（用詞已修正）**：
- `schema` = Gemini 看的定義
- `handler` = **stateless handler**：不依賴 request 外的 mutable state、不修改 application global state、不保存 session state；輸入明確、輸出 JSON serializable；**可以**呼叫外部 API；**可以**有受控的 module-level 唯讀快取（例如 TDX token + 過期時間，見風險 D）；**不可以**在模組頂層做任何可能失敗的初始化（client 物件一律 lazy init，用 `_get_client()` 之類的函式在第一次呼叫時才建立，不可在 import 時就執行）
- `policy`（可選）= 之後用於 authorization 分級（READ_ONLY / WRITE / DESTRUCTIVE），本週天氣插件全部唯讀，不填即可
- `REQUIRED_ENV` = import 成功後檢查，缺漏則該插件不註冊進 TOOLS/DISPATCH，但不影響其他插件

#### 3. Core（`ai_text.py`）

```python
from services.plugins import TOOLS, DISPATCH

MAX_TOOL_ROUNDS = 3        # Gemini 來回幾輪
MAX_TOOL_CALLS = 6         # 單次 request 總共執行幾個 tool call（一輪可能有多個 parallel call）
MAX_REQUEST_SECONDS = 25   # 單次 request 的硬性時間上限（配合 Render 300 秒 worker timeout 留足餘裕）

def chat(self, prompt, history=None):
    response = self._client.models.generate_content(...)
    return self._auto_handle_tool_calls(response)

def _auto_handle_tool_calls(self, response):
    # 內部依序：parse call → validate name in DISPATCH →
    # execute → normalize result → 回填 Gemini → repeat（受上述三個上限約束）
    # 中繼 function_call / function_response 只存在本次 request 記憶體 context，
    # 不寫入 chat_history；只有迴圈結束後的最終文字答案才觸發 SQLite 寫入
    ...
```

**動工前必須對照 google-genai SDK 實際版本核對 response 結構**：`content.parts` 為 list，每個 part 各自帶單數 `function_call`，多個工具呼叫時是多個 parts，不是單一 part 裡包一個 list。

#### 4. 環境變數 = 啟閉開關（改為明確白名單）

```
ENABLED_PLUGINS=weather  # 必填，逗號分隔；不再支援「留空 = 全部啟用」
```

`plugins/__init__.py` 啟動時讀此變數，只載入名單內的模組。不在名單 = 不載入 = 不佔 token、不暴露給 LLM、不執行健檢。**新增插件檔案後，若沒有把名稱加進 `ENABLED_PLUGINS`，該插件不會生效**——這是刻意設計，開發（新增檔案）與上線（加入白名單）分成兩個動作。

---

### 總結：架構介面的公開符號（定版）

| 符號 | 位置 | 用途 |
|------|------|------|
| `TOOLS: list[dict]` | `services.plugins` | 所有 function schema 扁平清單，給 Gemini |
| `DISPATCH: dict[str, callable]` | `services.plugins` | name → handler 映射，給 Tool Call Handler 執行 |
| `REQUIRED_ENV: list[str]` | 各插件模組 | 啟動驗證，缺漏自動禁用該插件 |
| `policy: dict`（可選） | 各插件 `TOOLS` 項目 | 授權分級佔位欄位，本週不使用，HackMD 上線前定義 |

---

## 第 1-1 部份：架構風險交叉檢查（定版，含新增風險 H）

> 風險 A–G 為原報告內容，維持原判並在此整合裁決結果；風險 H 為本版新增。

### 風險 A：`__init__.py` 自動掃描缺少容錯，可能拖垮全站

**問題**：任何插件在 import 階段丟例外（缺套件、語法錯、module-level 副作用）→ 整個 `services/plugins` import 失敗 → gunicorn worker boot 失敗 → 全站掛掉。

**修正**：掃描迴圈包 try/except；插件模組頂層不做任何可能失敗的初始化（client 必須 lazy init）；**新增：`DISPATCH` 賦值前檢查 key 是否已存在，重複視為 startup error；`callable(t["handler"])` 檢查，非 callable 視為該插件載入失敗**。

**注意（本版新增提醒）**：這條規則必須貫徹到所有插件範例，包含附錄中 HackMD 插件的 `_client = HackMDClient(...)` 這類模組頂層初始化寫法——那是違反本條規則的示範寫法，實作時需改為 lazy init。

### 風險 B：Tool-calling 迴圈的中繼結果會汙染 SQLite 歷史

**修正**：`_auto_handle_tool_calls()` 只有「最終文字答案」寫入 `chat_history`；中間的 function_call / function_response 只存在單次 request 記憶體 context，不落 SQLite。

### 風險 C：單一 Worker 的 timeout 風險被放大

**修正**：
- 所有 `requests`/`httpx` 呼叫 timeout 明確設 5–8 秒
- **`MAX_TOOL_ROUNDS`（來回輪數）、`MAX_TOOL_CALLS`（總呼叫數）、`MAX_REQUEST_SECONDS`（硬性時限）三者分開設定**（本版修正，原報告只有單一輪數上限）
- `plan_route_weather` 的多途徑點查詢考慮並行化

### 風險 D：TDX Token 快取 vs「stateless handler」的契約矛盾

**修正**：契約明文允許 module-level 的唯讀快取（token + 過期時間），明確禁止跨插件共享可變狀態。「快取允許，狀態互斥不允許」。

### 風險 E：HackMD asyncio 包裝方式有隱性風險

**修正**：不使用 `asyncio.get_event_loop()`；改用 `asyncio.run(coro)`。**記錄（本版）**：長期而言 Tool Call Handler 應該用 `inspect.iscoroutinefunction(handler)` 判斷是否 `await`，而不是強制所有 async handler 都包一層 `asyncio.run()`——此設計留到 hackmd.py 開工時再定案，不影響本週天氣插件。

### 風險 F：Gemini SDK function_call 解析語法需核對版本

**修正**：動工前務必對照當前 SDK 版本實際 response 結構驗證，`content.parts` 是 list，每個 part 各自帶單數 `function_call`。

### 風險 G：HackMD 寫入類工具需要使用者授權層

**修正**：dispatch 層需加「呼叫者身份檢查」。**本版補充**：授權不應是 HackMD 專屬邏輯，而是 `TOOLS` schema 裡 `policy` 欄位的一種取值（READ_ONLY / WRITE / DESTRUCTIVE），本週先在 schema 結構保留欄位、不實作分級邏輯，HackMD 上線前才需要 Tool Call Handler 真正讀取並執行這個欄位。

### 風險 H（本版新增）：Tool result 未經篩選直接進入 Gemini context

**問題**：即使中繼 function_call/function_response 不落 SQLite（風險 B 已解決），它們仍然會進入當次 Gemini request 的 context。若 handler 原樣回傳外部 API 的完整 response（例如 `get_nearby_cctv` 回傳附近全部 CCTV 清單、`get_rain_probability` 回傳整包 CWA JSON），會直接推高 token 用量與延遲，且惡化尚未被压测过的 tool-calling round-trip 對單 worker + 300 秒 timeout 架構的負擔。

**修正**：`services/weather_tools.py` 的每一支函式在 `return` 之前，都要把外部 API 的原始 response 篩選成 Gemini 真正需要的欄位（例如只留地點、機率、預報時間，不要整包 dataset metadata）。這一項與風險 C 一起列為本週 P0，理由是它同樣直接影響單 worker 架構的穩定性與回應延遲，且是本週就會發生（天氣 4 支 function 本身就會產生大小不一的外部 API response），不是延後到 tra/hackmd 才會出現的問題。

---

### 本週優先順序（定版）

| 優先級 | 項目 | 處理時機 |
|--------|------|----------|
| **P0** | A：import 容錯 + registry 完整性檢查（重複 name、非 callable） | 寫任何插件之前，先在 `__init__.py` 訂好 |
| **P0** | C：timeout + 三個上限（rounds/calls/seconds） | `weather_tools.py`、`ai_text.py` 第一版就設好 |
| **P0** | H：tool result 欄位篩選 | `weather_tools.py` 每支函式 return 前處理 |
| **P0** | `ENABLED_PLUGINS` 改為必填白名單 | `config.py` 這週就改，不留舊的「空 = 全開」邏輯 |
| **P1** | D：token 快取模式 | `get_nearby_cctv` 時定義，下週 tra.py 複用 |
| **P1** | F：SDK 結構驗證 | 動工前先對照 |
| **P1** | B：中繼資料不落 DB | `ai_text.py` 接入時同步處理 |
| **P2**（記錄不擋路） | E：asyncio 修正 + sync/async handler 支援 | 寫 hackmd.py 時才處理 |
| **P2**（記錄不擋路） | G：授權層（policy 欄位實際生效） | HackMD 上線前處理 |
| **P2**（記錄不擋路） | weather 邏輯與 `weathertools` 原專案分岔 | 若未來多處共用才考慮抽成 shared package |

---

## 第二部份：實作計畫 —— 天氣功能組（本週交付，定版）

### 現況分析

| 技能 | 核心函數 | 來源路徑 | 行號 | 依賴 | 環境變數 |
|------|----------|----------|------|------|----------|
| **降雨機率** | `fetch_rain_prob` | `SKILLS/cwa-weather-fetcher/scripts/fetch_weather.py` | 8–63 | `requests` | `CWA_API_KEY` |
| **GPS 天氣** | `_query_gps_weather` | `SKILLS/trip-weather-planner/scripts/plan_route_weather.py` | 102–134 | 外部 `weathertools/weather_gps.py` | `WEATHERTOOLS_ROOT` |
| **路線規劃** | `_query_gps_weather` + `_query_cctv_coverage` + `_format_output` | 同上 | 102–191, 292–306 | weather-gps-fetcher, tdx-cctv-weather | `WEATHERTOOLS_ROOT` |
| **CCTV 查詢** | `_query_cctv_coverage` | 同上 | 137–159 | 外部 `weathertools/weather_tdx.py` | `WEATHERTOOLS_ROOT` |

**關鍵問題**：GPS 天氣與 CCTV 兩技能為薄包裝層，真正邏輯在外部 `weathertools` 專案，必須內聯化才能在 Render 運作。（此分岔風險列為 P2，記錄不擋路。）

### 實作步驟（定版）

#### Step 1：建立插件基礎設施（一次性，P0）

| 檔案 | 用途 |
|------|------|
| `services/plugins/__init__.py` | 自動掃描 + try/except 容錯 + REQUIRED_ENV 驗證 + ENABLED_PLUGINS 白名單過濾 + **重複 tool name / handler callable 檢查（本版新增）** |
| `config.py` | 新增 `ENABLED_PLUGINS` 解析，**必填，不支援空值 = 全開** |

#### Step 2：建立 stateless handler 模組 `services/weather_tools.py`（P0：timeout + 欄位篩選）

| 函式 | 來源 | 處理方式 |
|------|------|----------|
| `get_rain_probability(location, dataset_id?, start_date?, end_date?)` | `cwa-weather-fetcher.fetch_rain_prob` | 直接移植，參數名稱標準化，**回傳前篩選欄位** |
| `get_gps_weather(lat, lon, station_count=3)` | `weathertools/weather_gps.py`（外部） | 內聯 HTTP 呼叫邏輯，移除 subprocess，**回傳前篩選欄位** |
| `plan_route_weather(route_name?, waypoints?)` | `trip-weather-planner` 編排邏輯 | 重寫為直接呼叫上述兩函式，載入 `routes.json` |
| `get_nearby_cctv(lat, lon, radius_km=2)` | `weathertools/weather_tdx.py`（外部） | 內聯 TDX API 呼叫邏輯，移除 subprocess，**回傳前篩選欄位（僅保留座標、路名、可用狀態等 Gemini 需要的欄位，不回傳完整 CCTV metadata）** |

所有 HTTP 呼叫 timeout = 5–8 秒（風險 C）。任何 client/session 物件一律 lazy init（風險 A）。

#### Step 3：建立插件檔案 `services/plugins/weather.py`

```python
from services.weather_tools import (
    get_rain_probability,
    get_gps_weather,
    plan_route_weather,
    get_nearby_cctv,
)

TOOLS = [
    {"schema": {...}, "handler": get_rain_probability},
    {"schema": {...}, "handler": get_gps_weather},
    {"schema": {...}, "handler": plan_route_weather},
    {"schema": {...}, "handler": get_nearby_cctv},
]

REQUIRED_ENV = ["CWA_API_KEY", "TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]
```

#### Step 4：修改 `ai_text.py` 接入插件系統

- 引入 `from services.plugins import TOOLS, DISPATCH`
- `chat()` 傳入 `tools=TOOLS`
- 實作 `_auto_handle_tool_calls()`，內部依序：parse call → 驗證 name 存在於 DISPATCH → execute → normalize result → 回填 Gemini → repeat
- 中繼 function_call/function_response 只存在記憶體 context，不落 SQLite；只有最終文字答案才進 `chat_history` 寫入流程
- 迴圈結構需對照 google-genai SDK 版本實際 response 結構（每個 part 各自帶 `function_call`，多工具 = 多 parts）
- **設定 `MAX_TOOL_ROUNDS = 3`、`MAX_TOOL_CALLS = 6`、`MAX_REQUEST_SECONDS = 25` 三個獨立上限（本版修正，取代原本單一輪數上限）**

#### Step 5：環境變數設定（Render Dashboard）

```
CWA_API_KEY=xxx
TDX_CLIENT_ID=xxx
TDX_CLIENT_SECRET=xxx
ENABLED_PLUGINS=weather
```

#### Step 6：部署驗證

- 傳送 `ai: 明天台南降雨機率` → 呼叫 `get_rain_probability`
- 傳送 `ai: 我現在在 24.99,121.45 附近天氣如何` → 呼叫 `get_gps_weather`
- 傳送 `ai: 幫我規劃台3線沿途天氣` → 呼叫 `plan_route_weather`
- 傳送 `ai: 這附近有沒有交通監視器` → 呼叫 `get_nearby_cctv`
- **新增驗證項**：檢查上述四次呼叫送進 Gemini 的 tool result 大小，確認已篩選欄位而非原樣回傳外部 API response
- **新增驗證項**：手動觸發 `ENABLED_PLUGINS` 缺漏環境變數的情境，確認插件正確跳過而非拖垮全站；手動製造重複 tool name，確認 registry 在 startup 階段報錯而非靜默覆蓋

---

## 第三部份：後續擴充規劃（下週、再下週，記錄不擋路）

### 下週：臺鐵查詢 (`services/plugins/tra.py`)

```python
TOOLS = [
    {"schema": {"name": "tra_search_trains", ...}, "handler": search_trains},
    {"schema": {"name": "tra_station_info", ...}, "handler": station_info},
    {"schema": {"name": "tra_fare", ...}, "handler": fare},
]
REQUIRED_ENV = ["TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]  # 重用既有
```

**Render 環境變數**：在 `ENABLED_PLUGINS` 加入 `tra`。

**本週已確立、下週可直接複用的部分**：TDX token 快取模式（風險 D）、registry validation 邏輯、tool result 欄位篩選慣例。

### 再下週：HackMD 筆記 (`services/plugins/hackmd.py`)

```python
TOOLS = [
    {"schema": {"name": "hackmd_search_notes", ...}, "handler": search_notes},
    {"schema": {"name": "hackmd_read_note", ...}, "handler": read_note},
    {"schema": {"name": "hackmd_create_note", ...}, "handler": create_note},
    {"schema": {"name": "hackmd_update_note", ...}, "handler": update_note, "policy": {"risk": "WRITE"}},
    {"schema": {"name": "hackmd_delete_note", ...}, "handler": delete_note, "policy": {"risk": "DESTRUCTIVE"}},
]
REQUIRED_ENV = ["HACKMD_API_TOKEN", "HACKMD_TEAM_URL"]
```

**Render 環境變數**：在 `ENABLED_PLUGINS` 加入 `hackmd`。

**HackMD 上線前必須解決（不可比照天氣插件簡化處理）**：
1. `policy` 欄位在 Tool Call Handler 層真正生效：`DESTRUCTIVE` 等級的呼叫需要額外的呼叫者身份檢查（比對 LINE user ID 是否為授權使用者）
2. Client 初始化改為 lazy init（不可沿用附錄範例的模組頂層 `_client = HackMDClient(...)` 寫法）
3. asyncio 包裝方式：優先評估 Tool Call Handler 用 `inspect.iscoroutinefunction` 判斷是否 `await`，而非強制所有 handler 走 `asyncio.run()`

---

## 附錄：4 個天氣技能詳細來源

### 1. get_rain_probability（降雨機率查詢）
- **絕對路徑**：`/usr/local/home/mimas/project/SKILLS/cwa-weather-fetcher/scripts/fetch_weather.py`
- **引用函數**：`fetch_rain_prob(api_key, dataset_id, location, start_date=None, end_date=None)`
- **行號**：8–63
- **依賴**：`requests`、`datetime`、`json`、`os`、`sys`、`argparse`
- **環境變數**：`CWA_API_KEY`
- **參考檔**：`/usr/local/home/mimas/project/SKILLS/cwa-weather-fetcher/references/dataset_mapping.md`（22 縣市 Dataset ID）

### 2. get_gps_weather（GPS 座標查詢）
- **絕對路徑**：`/usr/local/home/mimas/project/SKILLS/weather-gps-fetcher/scripts/fetch_gps_weather.py`
- **引用函數**：無獨立函數，邏輯在 `main()`（44–61 行）
- **核心邏輯**：`subprocess.run(["uv", "run", "weather_gps.py", ...])` 呼叫外部 `weathertools/weather_gps.py`
- **依賴**：`subprocess`、外部 weathertools 專案
- **環境變數**：`WEATHERTOOLS_ROOT`
- **需內聯**：`weathertools/weather_gps.py` 的 HTTP 呼叫與解析邏輯

### 3. plan_route_weather（路線規劃）
- **絕對路徑**：`/usr/local/home/mimas/project/SKILLS/trip-weather-planner/scripts/plan_route_weather.py`
- **引用函數**：
  - `_query_gps_weather(gps)`：102–134 行
  - `_query_cctv_coverage(gps)`：137–159 行
  - `_format_output()`：164–191 行
  - `_load_routes()`：67–83 行
  - `main()` 編排迴圈：292–306 行
- **依賴**：`subprocess`、`json`、`argparse`、`pathlib`、weather-gps-fetcher、tdx-cctv-weather 兩技能 CLI
- **環境變數**：`WEATHERTOOLS_ROOT`（間接）
- **參考檔**：`/usr/local/home/mimas/project/SKILLS/trip-weather-planner/references/routes.json`（3 條預設路線）

### 4. get_nearby_cctv（CCTV 查詢）
- **絕對路徑**：`/usr/local/home/mimas/project/SKILLS/tdx-cctv-weather/scripts/query_tdx_cctv.py`
- **引用函數**：無獨立函數，邏輯在 `main()`（46–66 行）
- **核心邏輯**：`subprocess.run(["uv", "run", "weather_tdx.py", ...])` 呼叫外部 `weathertools/weather_tdx.py`
- **依賴**：`subprocess`、外部 weathertools 專案
- **環境變數**：`WEATHERTOOLS_ROOT`、TDX 憑證（由外部讀取）
- **需內聯**：`weathertools/weather_tdx.py` 的 TDX API 呼叫邏輯

---

## 附錄：HackMD 筆記功能詳細來源（優先順序：最後）

### 現有資產分析

| 項目 | 內容 |
|------|------|
| **專案路徑** | `/usr/local/home/mimas/project/hackmd-agent-python/` |
| **核心模組** | `src/hackmd_agent/hackmd_client.py` |
| **操作規範** | `AGENTS.md` |
| **架構定位** | MCP Server，為 AI 提供操作 HackMD 筆記能力 |
| **開發語言** | Python 3.10+，全 async (httpx) |

### 現成功能對應表（`HackMDClient` 類別）

| 方法 | 功能 | 對應插件 Function | Policy（本版新增） |
|------|------|------------------|-----|
| `get_note_list()` | 取得所有筆記列表 | `hackmd_list_notes` | READ_ONLY |
| `get_note(note_id)` | 讀取單一筆記內容 | `hackmd_read_note` | READ_ONLY |
| `create_note(...)` | 建立新筆記 | `hackmd_create_note` | WRITE |
| `update_note(...)` | 更新既有筆記 | `hackmd_update_note` | WRITE |
| `delete_note(note_id)` | 刪除筆記 | `hackmd_delete_note` | DESTRUCTIVE |
| `search_notes(...)` | 搜尋筆記（標題/內文） | `hackmd_search_notes` | READ_ONLY |

### 共同基礎設施

| 元件 | 說明 |
|------|------|
| **重試機制** | `_request_with_retry()`：指數退避、支援 429/5xx、可配置 `max_retries`、`base_delay`、`max_delay` |
| **認證方式** | Bearer Token (`Authorization: Bearer {HACKMD_API_TOKEN}`) |
| **基礎 URL** | `https://api.hackmd.io/v1`（可覆蓋） |
| **非同步設計** | 所有 public method 為 `async`，使用 `httpx.AsyncClient` |
| **錯誤處理** | 401 → 檢查 token、429 → 退避重試、5xx → 重試、4xx → 直接拋出 |

### 整合優勢

| 項目 | 說明 |
|------|------|
| **零從零開發** | 成熟模組直接 `import`，已處理重試、認證、錯誤處理 |
| **MCP 相容** | 原專案即為 MCP Server 設計，符合工具呼叫範式 |
| **非同步優先** | 底層 async，插件層薄包裝即可同步/異步調用（見上方「HackMD 上線前必須解決」第 3 點） |
| **權限模型完整** | 支援 owner/signed_in/guest 三層讀寫權限，可直接對應 `policy` 欄位分級 |
| **搜尋靈活** | 標題搜尋快、全文搜尋可選、支援進度回呼 |

**注意**：此附錄的組裝範例（`_client = HackMDClient(...)` 模組頂層初始化）僅供理解 `HackMDClient` 介面，實際 `hackmd.py` 動工時必須改為 lazy init，不可照抄本附錄寫法（見「HackMD 上線前必須解決」第 2 點）。

---

*報告產生時間：2026-09-09*
*本版（a）為整合外部評審意見後的定版，取代原版 `CROSS_PROJECT_ANALYSIS_20260909.md` 作為施工規格*
