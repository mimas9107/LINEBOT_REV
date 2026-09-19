# 實作計畫（草案）：LINEBOT_REV HackMD 插件

> 依據 `CROSS_PROJECT_ANALYSIS_20260909a.md` 第三部份「再下週 HackMD」擴充；優先級調整：HackMD 提前，臺鐵（tra）挪到最後。

## 專案現況

- **插件系統**（rev2.4.5 已定版）：`services/plugins/__init__.py` 白名單載入 + REQUIRED_ENV 檢查 + registry 完整性檢查；`services/plugins/weather.py` 已有 4 支同步 handler 範例。
- **Tool Call Handler**（`services/ai_text.py`）：同步 loop，`handler(**args)` 直接呼叫；三上限（rounds/calls/seconds）；中繼不落 SQLite。
- **參考資產**：`hackmd-agent-python` 專案（v1.3.0）提供 `HackMDClient`（httpx AsyncClient + 429/5xx 指數退避重試）與 6 支工具；本環境 MCP 內也有平行實作的 HackMD 工具可對照驗證（欄位、行為、錯誤處理）。
- **部署**：Render 單 worker + 300s timeout；`requests`、`python-dotenv` 等已是最低依賴，`httpx` 目前不在 LINEBOT 的 `requirements.txt`。

---

## 決策定案（2026-09-19 討論結果）

| # | 決策 | 定案結果 |
|---|------|----------|
| D1 | HackMD 客戶端來源 | **內聯同步 client**：`services/hackmd_tools.py` 用既有 `requests` 實作 6 支 handler，不新增對外 git 依賴，可完全控管欄位篩選與 token sanitize |
| D2 | async 橋接方式 | **改核心支援 async**：`_auto_handle_tool_calls` 內部以 `inspect.iscoroutinefunction` 判斷 async handler 並 `await`；以單一 `asyncio.run()` 包住整個 tool loop（每 request 一個 loop）。今日 HackMD handler 全同步，async 支援為未來非同步 plugin 預留 |
| D3 | 授權模型 | **採納**：READ_ONLY 人人可用；WRITE/DESTRUCTIVE 需 LINE user ID 在 `HACKMD_ALLOWED_USER_IDS` 白名單；空名單 = 不開放任何寫入 |
| D4 | policy 生效位置 | **採納**：`_auto_handle_tool_calls` 執行前檢查 tool 的 `policy.risk` + 呼叫者身份；`user_id` 沿 `line_handler` → `chat_with_ai` → `chat()` → loop 傳遞；registry 匯出 `POLICY` map（name → risk），無記錄者預設 READ_ONLY |
| D5 | 版本 | **rev2.5.0**（main 偶數 MAJOR 政策） |

---

## 實作步驟總覽

| 階段 | 項目 | 檔案 | 優先級 |
|------|------|------|--------|
| 1 | HackMD 工具層 | `services/hackmd_tools.py` | P0 |
| 2 | HackMD 插件檔 | `services/plugins/hackmd.py` | P0 |
| 3 | Tool Call Handler 支援 async + policy（若 D2/D4 採納） | `services/ai_text.py`、`handlers/line_handler.py` | P0 |
| 4 | 環境變數 + 授權白名單 | `config.py`、`.env.example`、Render Dashboard | P0 |
| 5 | 部署驗證 | 手動測試 6 支 function | P0 |

---

## 詳細規格

### 階段 1：`services/hackmd_tools.py`（stateless handler 模組）

6 支 stateless handler，對應 `hackmd-agent-python` 現成功能，**回傳前欄位篩選**（沿用風險 H 慣例）：

| 函式 | 方式 | 回傳欄位（篩選後） |
|------|------|---------------------|
| `hackmd_list_notes()` | `GET /v1/notes` | 只留 `id`、`title`、`tags`、`createdAt` |
| `hackmd_read_note(note_id)` | `GET /v1/notes/{id}` | 只留 `id`、`title`、`content`（**內容加長度上限**，見風險 R-C） |
| `hackmd_create_note(title, content, read_permission?, write_permission?)` | `POST /v1/notes` | 只留 `id`、`title` |
| `hackmd_update_note(note_id, content, permissions?)` | `PATCH /v1/notes/{id}` | 只留 `id`、`title` |
| `hackmd_delete_note(note_id)` | `DELETE /v1/notes/{id}` | 回傳 `{"success": true, "id": ...}` |
| `hackmd_search_notes(keyword, search_content=False, fuzzy=False, limit=20)` | 本地過濾（取 list 後算相關性） | 只留 `id`、`title`（+ `_meta` 簡化版） |

**共同規範**：
- timeout：外部 HTTP 一律 8 秒（沿用 `weather_tools.DEFAULT_TIMEOUT`）
- 錯誤處理：統一回傳 `{"error": "..."}`，不拋例外給 loop
- 任何 client 物件 **lazy init**（風險 A 貫徹，模組頂層不建 client）
- TDX 式 module-level 唯讀快取：筆記清單 60s 快取（`search_notes`/`list_notes` 共用，寫入類操作後失效），「快取允許、狀態互斥不允許」
- 金鑰不外洩：錯誤訊息 sanitize（沿用 rev2.4.5 `_sanitize_error` 慣例）

### 階段 2：`services/plugins/hackmd.py`

- `REQUIRED_ENV = ["HACKMD_API_TOKEN"]`（D3 定案後追加授權白名單變數）
- `TOOLS`：6 支 schema，每支帶 `policy` 欄位：
  - READ_ONLY：`hackmd_list_notes` / `hackmd_read_note` / `hackmd_search_notes`
  - WRITE：`hackmd_create_note` / `hackmd_update_note`
  - DESTRUCTIVE：`hackmd_delete_note`
- schema 符合 Gemini Function Calling 規範（參考天氣插件寫法與 MCP 工具定義）

### 階段 3：Tool Call Handler 與呼叫者身份（取決於 D2/D4）

- 在 `ai_text.py` 的執行前檢查 `policy`：若 handler policy 非 READ_ONLY，比對當前 `user_id` 是否在 `HACKMD_ALLOWED_USER_IDS`；不在 → 回傳 `{"error": "此操作未經授權"}`，**不執行 handler**
- `user_id` 傳遞路徑：`line_handler._handle_text_message` → `chat_with_ai` → `AITextService.chat` → `_auto_handle_tool_calls`（新增參數或 context）
- 若 D2(b)：loop 中 `if inspect.iscoroutinefunction(handler): result = await handler(**args)`

### 階段 4：環境變數

- `HACKMD_API_TOKEN=...`（必填，缺漏則插件不載入）
- `HACKMD_ALLOWED_USER_IDS=...`（逗號分隔 LINE user IDs；空值 = 不開放任何 WRITE/DESTRUCTIVE）
- `ENABLED_PLUGINS=weather,hackmd`
- 同步更新 `.env.example`；Render Dashboard 設定

### 階段 5：部署驗證

- 6.1 功能：`ai: 我的 HackMD 筆記有哪些`、`ai: 讀取筆記 abc123`、`ai: 搜尋筆記「會議」`、`ai: 建立筆記 ...`、`ai: 更新筆記 ...`、`ai: 刪除筆記 ...`
- 6.2 架構：缺少 `HACKMD_API_TOKEN` → 插件跳過其餘正常；policy 未授權 user 試 WRITE → 被拒；重複 tool name → startup error
- 6.3 效能：單次 function 回應 < 10s；tool result 無完整 API response、「筆記內容」有長度上限

---

## 風險與對策

| # | 風險 | 等級 | 對策 |
|---|------|------|------|
| R-A | 客戶端來源：外掛 package 需對外可裝、且與本專案生命周期耦合 vs 內聯增加維護面 | P0 | 討論 D1；單人私有 bot 建議內聯最小同步 client（少依賴、可完全控管欄位篩選與 sanitize） |
| R-B | async client 與既有同步 loop 的橋接 | P0 | 討論 D2；「每次 `asyncio.run()` 新 loop」不需改核心、但要小心重複建 AsyncClient 的成本與 thread 安全 |
| R-C | note content 可能超大 → token 爆量 / timeout 被放大 | P0 | 回傳前內容截斷（如 2000 字元 + 提示被截斷）；沿用三上限 |
| R-D | HackMD 與 weather 插件並存時 registry 衝突 | P1 | 沿用既有重複 name raise；`ENABLED_PLUGINS=weather,hackmd` |
| R-E | 授權欄位與呼叫者身份缺漏 → 任意 user 可刪改筆記 | P0 | D3/D4 定案即解：WRITE/DESTRUCTIVE 預設關閉（白名單空值），READ_ONLY 才開放 |
| R-F | Plugin 與外部 `hackmd-agent-python` / MCP 工具分岔 | P2 | 記錄不擋路；以 MCP 工具行為為對照基準驗證（本 session 可直接呼叫 MCP hackmd 工具交叉比對） |

---

## 後續擴充（本版不排）

- `services/plugins/tra.py`（臺鐵 3 支 function）：挪到 HackMD 之後，TDX token 快取與場域慣例直接複用
- Tool Call Handler 拆分獨立 Executor 類別（P2）
- hackmd policy 升級：依使用者分級（owner / guest）取代單一白名單

---

*草案待討論定案後，才依本 PLAN 產出 `TASK.md`*