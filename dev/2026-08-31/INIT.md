# 📋 LINE Bot 503 容錯機制與歷史紀錄防污染更新計畫書

**專案標的：** `LINEBOT_REV`

**核心目標：** 解決 Google Gemini API 503 UNAVAILABLE 高負載導致 LINE Bot 異常，並修復「錯誤訊息污染 SQLite 對話歷史 DB」的缺陷。

**執行原則：** 遵循 MVP 最小可行性修改，採 Incremental Checkpoints（增量檢查點）推進，禁止重構非相關組件。

---

## 🎯 任務目標與變更範圍 (Scope)

1. **API 重試與備用機制 (Retry & Fallback):**

- 當主流模型 (`gemini-1.5-flash`) 回傳 503 (UNAVAILABLE) 或 429 (RATE_LIMIT) 時，進行退避重試 (Exponential Backoff)。
- 若多次重試失敗，自動降級調用備用模型 (`gemini-1.5-pro`)。

2. **對話歷史資料庫防污染 (Chat History Sanitization):**

- 嚴格隔離 AI 異常訊息。**僅有成功生成** 的模型回應才可寫入 `ChatHistory` 資料庫。
- 發生系統例外時，僅回覆 LINE 用戶友善提示，不留存錯誤 Trace 到 DB。

---

## 🚦 Agent 協作規範與約束 (Execution Constraints)

> **Agent 請嚴格遵守以下執行指令：**
>
> 1. **Rule 8 — 先問再寫：** 在提供修改代碼前，若需要確認 `AITextService` 或 `LineHandler` 的具體 Method 簽名或檔案結構，請先向使用者索取該段程式碼。
> 2. **Rule 3 — 手術式 Snippet (Slot-Based):** 僅提供受影響函式的修訂程式碼，禁止列出未變更的上下文或整檔重寫。
> 3. **Rule 12 — 失敗顯性 (Fail Loud):** 若遇到邊界條件不明（例如 SQLite 欄位設計未知），請直接停止並提出疑問，禁止盲目假設。
> 4. **Verification Checkpoint:** 每次交付程式碼後，必須附帶本地驗證 (Verification) 的步驟與測試情境。

---

## 階段式執行步驟 (Incremental Execution Steps)

```
[Phase 1: 上下文收集] ➔ [Phase 2: AITextService 改造] ➔ [Phase 3: LineHandler 歷史隔離] ➔ [Phase 4: 本地驗證]

```

### Phase 1: 上下文採集與對齊 (Context Gathering)

- **Agent 任務：** 請 Agent 列出實作此變更所需檢視的具體檔案名稱與函式片段（如：`services/ai_service.py` 與 `handlers/line_handler.py`）。
- **Checkpoint 1：** 使用者提供對應的關鍵程式碼片段，Agent 確認理解業務意圖後方可推進。

### Phase 2: AITextService 實現 Retry & Fallback

- **Agent 任務：** 為 Gemini API 調用邏輯封裝 Retry 機制。
- **主模型：** `gemini-1.5-flash`
- **備用模型：** `gemini-1.5-pro`
- **捕捉例外：** `503 Service Unavailable`, `429 Too Many Requests`
- **退避策略：** 重試 2 次，間隔 `1.5s * attempt`

- **Checkpoint 2：** Agent 提供 `AITextService` 的手術式修訂 Snippet，並說明 Exception 傳播邏輯。

### Phase 3: LineHandler 防污染邏輯改造

- **Agent 任務：** 調整 `LineHandler` 的 Try-Except 流程。
- **成功路徑：** 取得 AI 回覆 ➔ 寫入 DB (`ChatHistory.save`) ➔ 回覆 LINE 用戶。
- **失敗路徑：** 捕捉 `RuntimeError` / `APIError` ➔ **跳過 DB 寫入** ➔ 回覆 LINE 用戶「伺服器繁忙，請稍後再試」。

- **Checkpoint 3：** Agent 提供 `LineHandler` 受影響區塊的 Slot-based Snippet。

### Phase 4: 本地驗證與單元檢核 (Verification)

- **Agent 任務：** 提供情境測試指令與 Local 驗證腳本，協助使用者在本地端模擬 503 拋錯。
- **驗證指標：**

1. 模擬 API 拋出 503 時，系統是否自動重試或切換模型。
2. 模擬 API 完全失敗時，SQLite `ChatHistory` 資料表中**未增加**含有 `503 UNAVAILABLE` 的紀錄。

---

## 💬 傳送給 Agent 的起始指令 (Copy & Paste)

您可以直接複製以下框內的文字發給您的 AI Agent 開始執行：

```text
Hi Agent，我們需要為 LINEBOT_REV 進行 503 容錯與歷史紀錄防污染的更新。
請詳細閱讀以下專案計畫書，並嚴格遵循其中的規範（先問再寫、手術式修改、每個 Phase 建立 Checkpoint）：

【計畫書內容開始】
(貼上本份計畫書全文)
【計畫書內容結束】

現在讓我們從 Phase 1 開始。請告訴我你需要查看哪些檔案或函式片段來開始規劃修改？

```
