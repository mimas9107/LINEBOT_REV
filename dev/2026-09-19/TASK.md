# 任務清單：LINEBOT_REV HackMD 插件（rev2.5.0）

> 依據 `PLAN.md`（2026-09-19 定案）拆解為可執行的原子任務，每項可獨立驗證
> 決策定案：D1 內聯同步 client / D2 核心支援 async / D3+D4 授權白名單 / D5 rev2.5.0 / D6 SPEC 機制化解耦 / D7 身份標的語義
>
> ## 狀態：CLOSE
>
> - 結案日期：2026-09-23
> - 交付版本：rev2.4.5 → rev2.5.0（commit 洽本次結案 commit）
> - 驗證結果：部署上 Render 後，`hackmd_search_notes` 命中 icecc 筆記、`hackmd_read_note` 回傳截斷 content（2000 字 + truncated）實測通過；授權 user（U6433…5e8）gate pass；phased 驗證 5.1/5.2/5.3/5.4 勾選
> - 結案補齊：spec/README/CHANGELOG/MEMOIR 同步至 rev2.5.0

---

## 階段 1：`services/hackmd_tools.py`（內聯同步 handler 模組，D1）

### 1.1 共用基礎設施
- [x] 建立 `_get_client()` lazy init：`requests.Session`（timeout=8.0），模組頂層不初始化
- [x] 共用 `DEFAULT_TIMEOUT = 8.0`
- [x] 檔案頂部定義 `HACKMD_API_URL = "https://api.hackmd.io/v1"`
- [x] 共用錯誤處理：統一回傳 `{"error": "..."}` dict 而非拋出例外
- [x] 共用 sanitize：錯誤訊息不回帶 `Authorization` / Bearer token（沿用 `weather_tools._sanitize_error` 慣例）
- [x] 筆記清單 60 秒 module-level 唯讀快取（供 `list_notes` / `search_notes` 共用）；寫入類操作後失效
- [x] 回傳前欄位篩選（置於各 handler 內）＋ note content 長度上限（2000 字元，超出截斷並註記）

### 1.2 `hackmd_list_notes()`
- [x] `GET /notes`，Bearer token 認證
- [x] **欄位篩選**：只留 `{"id", "title", "tags", "created_at"}` 的 list（實作以 API 實際欄位 `createdAt` 為準）
- [x] 錯誤回傳：`{"error": "..."}`

### 1.3 `hackmd_read_note(note_id)`
- [x] `GET /notes/{note_id}`
- [x] 參數驗證：`note_id` 必填，缺失回傳 `{"error": "note_id is required"}`
- [x] **欄位篩選**：只留 `{"id", "title", "content"}`，content 截斷至上限
- [x] 錯誤回傳：`{"error": "..."}`

### 1.4 `hackmd_create_note(title, content, read_permission=None, write_permission=None)`
- [x] `POST /notes`，body 含 title/content/readPermission/writePermission（後兩者選填）
- [x] 參數驗證：title、content 必填
- [x] **欄位篩選**：只留 `{"id", "title"}`
- [x] 成功後失效 notes 快取
- [x] 錯誤回傳：`{"error": "..."}`

### 1.5 `hackmd_update_note(note_id, content, read_permission=None, write_permission=None)`
- [x] `PATCH /notes/{note_id}`，body 含 content 與選填權限
- [x] 參數驗證：note_id、content 必填
- [x] **欄位篩選**：只留 `{"id", "title"}`
- [x] 成功後失效 notes 快取
- [x] 錯誤回傳：`{"error": "..."}`

### 1.6 `hackmd_delete_note(note_id)`
- [x] `DELETE /notes/{note_id}`
- [x] 參數驗證：note_id 必填
- [x] 回傳 `{"success": true, "id": note_id}`
- [x] 成功後失效 notes 快取
- [x] 錯誤回傳：`{"error": "..."}`

### 1.7 `hackmd_search_notes(keyword, search_content=False, fuzzy=False, limit=20)`
- [x] 參數驗證：keyword 必填
- [x] 以 notes 快取/list 為來源，本地計算相關性排序（標題完整匹配 > 開頭 > 包含 > 字詞；模糊比對可選）
- [x] `search_content=True` 時逐筆呼叫 `read_note` 比對 content（受 `MAX_CONTENT_SCAN=20` 與上限保護）
- [x] **欄位篩選**：只留 `{"id", "title"}`（+ `_meta` 相關性分數）
- [x] `limit` 上限 100
- [x] 錯誤回傳：`{"error": "..."}`

---

## 階段 2：`services/plugins/hackmd.py`

### 2.1 建置插件檔案
- [x] 匯入 `services.hackmd_tools` 6 支 handler
- [x] 定義 `REQUIRED_ENV = ["HACKMD_API_TOKEN"]`
- [x] 定義 `TOOLS` 列表（6 支 schema），每支帶 **`"policy": {"risk": "..."}`** 欄位：
  - [x] `hackmd_list_notes` → READ_ONLY
  - [x] `hackmd_read_note` → READ_ONLY
  - [x] `hackmd_search_notes` → READ_ONLY
  - [x] `hackmd_create_note` → WRITE
  - [x] `hackmd_update_note` → WRITE
  - [x] `hackmd_delete_note` → DESTRUCTIVE
- [x] schema 的 `description`、`parameters` 符合 Gemini Function Calling 規範（參數沿用既有 snake_case 慣例對齊 handler 簽名，與 weather 插件一致）

---

## 階段 3：Registry 與 Tool Call Handler（D2 + D4）

### 3.1 `services/plugins/__init__.py`
- [x] 匯出 `POLICY: dict[str, str]`（tool name → risk 等級）
- [x] 載入 TOOLS 時同時填充 POLICY（`tool.get("policy", {}).get("risk", "READ_ONLY")`）
- [x] 維持既有 registry 完整性檢查（重複 name raise、非 callable 跳過）

### 3.2 `services/ai_text.py` 支援 async handler（D2）
- [x] `_auto_handle_tool_calls` 內部處理既存同步 handler：`result = handler(**args)`
- [x] `inspect.iscoroutinefunction(handler)` 為 True 時改 `await handler(**args)`
- [x] 以單一 `asyncio.run()` 包住整個 tool loop（`chat()` 內呼叫處），今日無 async handler 時行為不變

### 3.3 `services/ai_text.py` 授權檢查（D3 + D4 + D7）
- [x] 執行 handler 前檢查 `POLICY.get(name)`：
  - [x] READ_ONLY（或缺省）→ 直接執行
  - [x] WRITE / DESTRUCTIVE → 先看 `user_scope`：group/room 一律拒絕（群組唯讀）；僅 user 身份比對 `user_id` 是否在 `HACKMD_ALLOWED_USER_IDS`；不在 → 回傳 `{"error": "此操作未經授權"}` 且**不執行 handler**
- [x] `chat()` / `_auto_handle_tool_calls` 新增 `user_id: str = ""`、`user_scope: str = "user"` 參數（預設值保留向後相容）
- [x] `chat_with_ai(prompt, history=None, user_id="", user_scope="user")` 透傳

### 3.4 `handlers/line_handler.py`
- [x] `_handle_text_message` 依 `event.source.type` 決定 `user_scope`（user/group/room），呼叫 `chat_with_ai(full_prompt, user_id=user_id, user_scope=user_scope)`
- [x] 確認既有呼叫點不破（`c:`/`提醒` 路徑不影響）

---

## 階段 4：環境變數與設定

### 4.1 `config.py`
- [x] 新增 `HACKMD_API_TOKEN: str = ""` + `__post_init__` 載入
- [x] 新增 `HACKMD_ALLOWED_USER_IDS: str = ""` + `__post_init__` 載入
- [x] 新增 property `allowed_user_ids_list` 回傳 `list[str]`（逗號分隔、strip、過濾空值）

### 4.2 `.env.example`
- [x] 新增 `HACKMD_API_TOKEN=...`
- [x] 新增 `HACKMD_ALLOWED_USER_IDS=...`（註明空值 = 不開放寫入）
- [x] `ENABLED_PLUGINS` 範例改為 `weather,hackmd`

### 4.3 Render Dashboard（手動）
- [ ] 設定 `HACKMD_API_TOKEN`、`HACKMD_ALLOWED_USER_IDS`
- [ ] `ENABLED_PLUGINS=weather,hackmd`

---

## 階段 5：驗證測試

### 5.1 功能測試
- [x] `ai: 我的 HackMD 筆記有哪些` → `hackmd_list_notes`，回傳精簡欄位
- [x] `ai: 讀取筆記 <note_id>` → `hackmd_read_note`，content 有長度上限（實測 saw 2000 字 + truncated）
- [x] `ai: 搜尋 HackMD 筆記「會議」` → `hackmd_search_notes`，回傳精簡欄位（實測命中 icecc 筆記）
- [x] `ai: 建立一則標題為「測試」的筆記...`（授權 user）→ `hackmd_create_note` 成功
- [x] `ai: 更新筆記 <note_id> 內容...`（授權 user）→ `hackmd_update_note` 成功
- [x] `ai: 刪除筆記 <note_id>`（授權 user）→ `hackmd_delete_note` 成功

### 5.2 授權驗證
- [x] 非授權 user 觸發 `hackmd_create_note` → 回傳「此操作未經授權」且 **HackMD 端無新增**
- [x] 授權 user 觸發 `hackmd_delete_note` → 成功
- [x] READ_ONLY（list/read/search）任一 user 皆可用
- [x] 群組/聊天室身份觸發任何 WRITE/DESTRUCTIVE → 一律拒絕（群組唯讀）
- [x] 群組/聊天室身份使用 list/read/search → 正常可用

### 5.3 架構驗證
- [x] 移除 `HACKMD_API_TOKEN` → `hackmd` 插件跳過、weather 正常、不報錯（本地 `env -u` 驗證）
- [x] `ENABLED_PLUGINS=weather,hackmd` → 兩插件同時載入、registry 無衝突（10 支工具）
- [x] 人為製造重複 tool name → 啟動時 `RuntimeError`（既有檢查保留）
- [x] 檢查 SQLite：中繼 function_call/response 不存在，只有最終文字答案

### 5.4 效能驗證
- [x] 6 支 function 回應時間 < 10 秒（實測單輪呼叫於數秒內完成）
- [x] tool result 大小合理（無完整 HTTP response、長 content 已截斷、無 token 洩漏）

---

## 階段 6：SPEC 機制化解耦與文件同步（D6/D7）

### 6.1 SPEC.md 機制化
- [x] plugin 條文抽離 weather 工具清單，改為純機制描述（載入白名單、重複 name raise、REQUIRED_ENV、三上限、per-tool risk 分級執行前檢查、async 支援）
- [x] 更新 header 戳記：`modified_date`、`document_version` 遞增（`project_version` 留待 release 改 2.5.0）

### 6.2 資產清單移轉到 README
- [x] README 建立「啟用插件工具清單」：weather 4 支 + hackmd 6 支（名稱 / 用途 / 權限等級）
- [x] 確認 SPEC 內已無任何工具清單式描述

### 6.3 群組身份語義文件化（D7）
- [x] README 或 plugin 文件註記 `_get_user_id()` 的 user/group/room 語義
- [x] 註明 `HACKMD_ALLOWED_USER_IDS` 填寫規則：僅個人身份（user）可比對白名單
- [x] 註明群組/聊天室一律唯讀：WRITE/DESTRUCTIVE 全禁、DESTRUCTIVE 對任何非個人身份一律拒絕

---

## 完成定義

- [x] 所有 P0 任務勾選完成
- [x] 部署到 Render 通過健康檢查
- [x] 6 支 function 實測正確回應
- [x] 授權驗證 3 項通過（含未授權被拒）
- [x] SPEC 機制化完成：無工具資產清單、僅機制條文；README 收錄 weather+hackmd 共 10 支工具清單與群組身份語義
- [x] 更新 `CHANGELOG.md`、`README.md`、`SPEC.md`、`MEMOIR.md` 版本號（2.4.5 → 2.5.0）與內容