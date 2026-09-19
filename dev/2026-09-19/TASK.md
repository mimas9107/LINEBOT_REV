# 任務清單：LINEBOT_REV HackMD 插件（rev2.5.0）

> 依據 `PLAN.md`（2026-09-19 定案）拆解為可執行的原子任務，每項可獨立驗證
> 決策定案：D1 內聯同步 client / D2 核心支援 async / D3+D4 授權白名單 / D5 rev2.5.0

---

## 階段 1：`services/hackmd_tools.py`（內聯同步 handler 模組，D1）

### 1.1 共用基礎設施
- [ ] 建立 `_get_client()` lazy init：`requests.Session`（timeout=8.0），模組頂層不初始化
- [ ] 共用 `DEFAULT_TIMEOUT = 8.0`
- [ ] 檔案頂部定義 `HACKMD_API_URL = "https://api.hackmd.io/v1"`
- [ ] 共用錯誤處理：統一回傳 `{"error": "..."}` dict 而非拋出例外
- [ ] 共用 sanitize：錯誤訊息不回帶 `Authorization` / Bearer token（沿用 `weather_tools._sanitize_error` 慣例）
- [ ] 筆記清單 60 秒 module-level 唯讀快取（供 `list_notes` / `search_notes` 共用）；寫入類操作後失效
- [ ] 回傳前欄位篩選（置於各 handler 內）＋ note content 長度上限（如 2000 字元，超出截斷並註記）

### 1.2 `hackmd_list_notes()`
- [ ] `GET /notes`，Bearer token 認證
- [ ] **欄位篩選**：只留 `{"id", "title", "tags", "created_at"}` 的 list
- [ ] 錯誤回傳：`{"error": "..."}`

### 1.3 `hackmd_read_note(note_id)`
- [ ] `GET /notes/{note_id}`
- [ ] 參數驗證：`note_id` 必填，缺失回傳 `{"error": "note_id is required"}`
- [ ] **欄位篩選**：只留 `{"id", "title", "content"}`，content 截斷至上限
- [ ] 錯誤回傳：`{"error": "..."}`

### 1.4 `hackmd_create_note(title, content, read_permission=None, write_permission=None)`
- [ ] `POST /notes`，body 含 title/content/readPermission/writePermission（後兩者選填）
- [ ] 參數驗證：title、content 必填
- [ ] **欄位篩選**：只留 `{"id", "title"}`
- [ ] 成功後失效 notes 快取
- [ ] 錯誤回傳：`{"error": "..."}`

### 1.5 `hackmd_update_note(note_id, content, read_permission=None, write_permission=None)`
- [ ] `PATCH /notes/{note_id}`，body 含 content 與選填權限
- [ ] 參數驗證：note_id、content 必填
- [ ] **欄位篩選**：只留 `{"id", "title"}`
- [ ] 成功後失效 notes 快取
- [ ] 錯誤回傳：`{"error": "..."}`

### 1.6 `hackmd_delete_note(note_id)`
- [ ] `DELETE /notes/{note_id}`
- [ ] 參數驗證：note_id 必填
- [ ] 回傳 `{"success": true, "id": note_id}`
- [ ] 成功後失效 notes 快取
- [ ] 錯誤回傳：`{"error": "..."}`

### 1.7 `hackmd_search_notes(keyword, search_content=False, fuzzy=False, limit=20)`
- [ ] 參數驗證：keyword 必填
- [ ] 以 notes 快取/list 為來源，本地計算相關性排序（標題完整匹配 > 開頭 > 包含 > 字詞；模糊比對可選）
- [ ] `search_content=True` 時逐筆呼叫 `read_note` 比對 content（受快取與上限保護，避免過多呼叫）
- [ ] **欄位篩選**：只留 `{"id", "title"}`（+ 相關性分數可選）
- [ ] `limit` 上限 100
- [ ] 錯誤回傳：`{"error": "..."}`

---

## 階段 2：`services/plugins/hackmd.py`

### 2.1 建置插件檔案
- [ ] 匯入 `services.hackmd_tools` 6 支 handler
- [ ] 定義 `REQUIRED_ENV = ["HACKMD_API_TOKEN"]`
- [ ] 定義 `TOOLS` 列表（6 支 schema），每支帶 **`"policy": {"risk": "..."}`** 欄位：
  - [ ] `hackmd_list_notes` → READ_ONLY
  - [ ] `hackmd_read_note` → READ_ONLY
  - [ ] `hackmd_search_notes` → READ_ONLY
  - [ ] `hackmd_create_note` → WRITE
  - [ ] `hackmd_update_note` → WRITE
  - [ ] `hackmd_delete_note` → DESTRUCTIVE
- [ ] schema 的 `description`、`parameters` 符合 Gemini Function Calling 規範（參數名用 camelCase 對齊 MCP 工具：noteId / readPermission / writePermission / searchContent）

---

## 階段 3：Registry 與 Tool Call Handler（D2 + D4）

### 3.1 `services/plugins/__init__.py`
- [ ] 匯出 `POLICY: dict[str, str]`（tool name → risk 等級）
- [ ] 載入 TOOLS 時同時填充 POLICY（`tool.get("policy", {}).get("risk", "READ_ONLY")`）
- [ ] 維持既有 registry 完整性檢查（重複 name raise、非 callable 跳過）

### 3.2 `services/ai_text.py` 支援 async handler（D2）
- [ ] `_auto_handle_tool_calls` 內部處理既存同步 handler：`result = handler(**args)`
- [ ] `inspect.iscoroutinefunction(handler)` 為 True 時改 `await handler(**args)`
- [ ] 以單一 `asyncio.run()` 包住整個 tool loop（`chat()` 內呼叫處），今日無 async handler 時行為不變

### 3.3 `services/ai_text.py` 授權檢查（D3 + D4）
- [ ] 執行 handler 前檢查 `POLICY.get(name)`：
  - [ ] READ_ONLY（或缺省）→ 直接執行
  - [ ] WRITE / DESTRUCTIVE → 檢查 `user_id` 是否在 `HACKMD_ALLOWED_USER_IDS`；不在 → 回傳 `{"error": "此操作未經授權"}` 且**不執行 handler**
- [ ] `chat()` / `_auto_handle_tool_calls` 新增 `user_id: str = ""` 參數（預設空字串，保留向後相容）
- [ ] `chat_with_ai(prompt, history=None, user_id="")` 透傳 user_id

### 3.4 `handlers/line_handler.py`
- [ ] `_handle_text_message` 呼叫 `chat_with_ai(full_prompt, user_id=user_id)`（或既有 history 參數合併傳入）
- [ ] 確認既有呼叫點不破（`c:`/`提醒` 路徑不影響）

---

## 階段 4：環境變數與設定

### 4.1 `config.py`
- [ ] 新增 `HACKMD_API_TOKEN: str = ""` + `__post_init__` 載入
- [ ] 新增 `HACKMD_ALLOWED_USER_IDS: str = ""` + `__post_init__` 載入
- [ ] 新增 property `allowed_user_ids_list` 回傳 `list[str]`（逗號分隔、strip、過濾空值）

### 4.2 `.env.example`
- [ ] 新增 `HACKMD_API_TOKEN=...`
- [ ] 新增 `HACKMD_ALLOWED_USER_IDS=...`（註明空值 = 不開放寫入）
- [ ] `ENABLED_PLUGINS` 範例改為 `weather,hackmd`

### 4.3 Render Dashboard（手動）
- [ ] 設定 `HACKMD_API_TOKEN`、`HACKMD_ALLOWED_USER_IDS`
- [ ] `ENABLED_PLUGINS=weather,hackmd`

---

## 階段 5：驗證測試

### 5.1 功能測試
- [ ] `ai: 我的 HackMD 筆記有哪些` → `hackmd_list_notes`，回傳精簡欄位
- [ ] `ai: 讀取筆記 <note_id>` → `hackmd_read_note`，content 有長度上限
- [ ] `ai: 搜尋 HackMD 筆記「會議」` → `hackmd_search_notes`，回傳精簡欄位
- [ ] `ai: 建立一則標題為「測試」的筆記...`（授權 user）→ `hackmd_create_note` 成功
- [ ] `ai: 更新筆記 <note_id> 內容...`（授權 user）→ `hackmd_update_note` 成功
- [ ] `ai: 刪除筆記 <note_id>`（授權 user）→ `hackmd_delete_note` 成功

### 5.2 授權驗證
- [ ] 非授權 user 觸發 `hackmd_create_note` → 回傳「此操作未經授權」且 **HackMD 端無新增**
- [ ] 授權 user 觸發 `hackmd_delete_note` → 成功
- [ ] READ_ONLY（list/read/search）任一 user 皆可用

### 5.3 架構驗證
- [ ] 移除 `HACKMD_API_TOKEN` → `hackmd` 插件跳過、weather 正常、不報錯
- [ ] `ENABLED_PLUGINS=weather,hackmd` → 兩插件同時載入、registry 無衝突
- [ ] 人為製造重複 tool name → 啟動時 `RuntimeError`
- [ ] 檢查 SQLite：中繼 function_call/response 不存在，只有最終文字答案

### 5.4 效能驗證
- [ ] 6 支 function 回應時間 < 10 秒
- [ ] tool result 大小合理（無完整 HTTP response、長 content 已截斷、無 token 洩漏）

---

## 完成定義

- [ ] 所有 P0 任務勾選完成
- [ ] 部署到 Render 通過健康檢查
- [ ] 6 支 function 實測正確回應
- [ ] 授權驗證 3 項通過（含未授權被拒）
- [ ] 更新 `CHANGELOG.md`、`README.md`、`SPEC.md`、`MEMOIR.md` 版本號（2.4.5 → 2.5.0）與內容