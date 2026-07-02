---
name:          "IMPROVE_TASK.md"
description:   "改善任務清單（依效能影響優先排序）"
created_date:  "2026/07/02"
modified_date: "2026/07/02"
project_version: "2.1.0"
---

# IMPROVE_TASK — LINEBOT_REV 改善任務清單

> 依效能影響由高至低排序。完成後請更新 `status` 並記錄於 CHANGELOG.md。

---

## Task #1 — `save_message` 非同步化（阻塞主線程）

| 欄位 | 內容 |
|------|------|
| **Priority** | 🔴 P1 — 效能 |
| **Status** | `[x] DONE` |
| **影響檔案** | `services/bookmark.py` L93 |
| **影響範圍** | 每則訊息回覆都被拖慢 |

### 問題描述

`save_message()` 在 LINE handler 主流程中同步呼叫，包含：
- `time.sleep(0.25)` 強制等待
- `requests.post(..., timeout=30)` 同步 HTTP 請求至 GAS

當 GAS 回應慢或逾時，整個 webhook handler 會被卡住，導致 LINE 回覆延遲甚至失敗。

### 修正方向

將 `save_message` 改為背景執行緒呼叫，讓 AI 回覆與資料寫入並行：

```python
# handlers/line_handler.py
import threading

# 非同步儲存，不阻塞主線程
threading.Thread(
    target=save_message,
    args=(timestamp, user_id, message_type, message_text),
    daemon=True
).start()
```

同時移除 `bookmark.py` 中的 `time.sleep(0.25)`，改由 GAS 端的冪等寫入機制保證資料完整性。

### 驗收標準

- [ ] `save_message` 呼叫不阻塞 LINE 回覆流程
- [ ] 移除或遷移 `time.sleep(0.25)`
- [ ] 測試：快速連續送出兩則訊息，兩則都能即時收到 AI 回覆

---

## Task #2 — 修正 GAS catch 區塊塊 `error` 未定義

| 欄位 | 內容 |
|------|------|
| **Priority** | 🔴 P2 — Bug |
| **Status** | `[x] DONE` |
| **影響檔案** | `google_app_script/linebot.gs` L79, L106 |
| **影響範圍** | 錯誤發生時，GAS 二次爆炸，Python 端收到非預期回應 |

### 問題描述

catch 區塊用 `err` 接住例外，但 return 時誤用未定義的 `error` 變數：

```javascript
// ❌ 錯誤：error 未定義，會再次拋出 ReferenceError
} catch(err) {
    return ContentService.createTextOutput(
        JSON.stringify({"status": "error", "message": error.toString()})
    ).setMimeType(ContentService.MimeType.JSON);
}
```

### 修正方向

```javascript
// ✅ 修正：改用 err
} catch(err) {
    return ContentService.createTextOutput(
        JSON.stringify({"status": "error", "message": err.toString()})
    ).setMimeType(ContentService.MimeType.JSON);
}
```

L79 與 L106 兩處皆需修正。

### 驗收標準

- [ ] L79 `error.toString()` → `err.toString()`
- [ ] L106 `error.toString()` → `err.toString()`
- [ ] 故意製造錯誤（如 JSON 格式錯誤）驗證 GAS 能正確回傳 error JSON

---

## Task #3 — 修正歷史對話角色判斷邏輯（Bot 回覆未存入）

| 欄位 | 內容 |
|------|------|
| **Priority** | 🔴 P3 — Bug / AI 品質 |
| **Status** | `[x] DONE` |
| **影響檔案** | `services/ai_text.py` L134、`google_app_script/linebot.gs`、`handlers/line_handler.py` |
| **影響範圍** | Gemini 多輪對話歷史格式錯誤，AI 無法理解上下文 |

### 問題描述

目前 GAS 只存使用者訊息，Bot 回覆未被寫入 Google Sheets。
`_convert_history_to_contents()` 以「第一筆 userId 為 user」判斷角色，
導致送給 Gemini 的歷史全為 `role: user`，違反 Gemini API 交替格式要求。

### 修正方向

**方案 A（推薦）：讓 Python 端在 AI 回覆後，將 Bot 回覆也寫入 Sheets**

```python
# handlers/line_handler.py — AI 回覆後額外儲存 Bot 的回應
result = chat_with_ai(full_prompt)
save_message(timestamp, "bot", "text", result)  # 加入 bot 回覆
```

GAS 端 `getChatHistory` 不需修改，自然會取到 user/bot 交替記錄。

`_convert_history_to_contents()` 改為以 `userId == "bot"` 判斷 model 角色：

```python
role = 'model' if entry.get('userId') == 'bot' else 'user'
```

**方案 B：改用 in-memory 對話歷史（不依賴 GAS）**
- 使用 `client.chats.create()` 管理 session，以 user_id 為 key 存入記憶體
- 缺點：服務重啟後歷史消失

### 驗收標準

- [ ] Google Sheets 中可見 bot 回覆記錄（userId = "bot"）
- [ ] `_convert_history_to_contents` 正確輸出 user/model 交替角色
- [ ] 實測多輪對話（ai: 你好 → ai: 我剛說了什麼）能正確延續上下文

---

## Task #4 — 圖片路徑改用 message_id 防止並發覆蓋

| 欄位 | 內容 |
|------|------|
| **Priority** | 🟡 P4 — 穩定性 |
| **Status** | `[x] DONE` |
| **影響檔案** | `handlers/line_handler.py` L184、`config.py` L38 |
| **影響範圍** | 多人同時上傳圖片時，後者覆蓋前者，AI 分析到錯誤圖片 |

### 問題描述

`DOWNLOAD_IMAGE_PATH` 固定為 `pic/downloadimg.jpg`，
所有使用者共用同一個檔案路徑，並發場景下會互相覆蓋。

### 修正方向

```python
# handlers/line_handler.py — _download_image 動態產生唯一路徑
def _download_image(self, message_id: str) -> str:
    image_path = f"pic/{message_id}.jpg"   # 以 message_id 為唯一檔名
    ...
    # 分析完畢後刪除暫存檔（在 _handle_image_message 中呼叫）
    os.remove(image_path)
```

### 驗收標準

- [ ] 圖片儲存路徑包含 `message_id`（如 `pic/12345678.jpg`）
- [ ] 分析完畢後自動清除暫存圖片，避免磁碟累積
- [ ] 移除或廢棄 `config.py` 中的 `DOWNLOAD_IMAGE_PATH` 常數

---

## Task #5 — 修正 README 模型版本記載不一致

| 欄位 | 內容 |
|------|------|
| **Priority** | 🟢 P5 — 文件 |
| **Status** | `[x] DONE` |
| **影響檔案** | `README.md` L29, L111, L167, L180 |
| **影響範圍** | 維護者閱讀混淆，不影響執行 |

### 問題描述

`config.py` 已改用 `gemini-flash-latest` 別名，但 README 多處仍記載 `gemini-2.5-flash`。

### 修正方向

全文搜尋 `gemini-2.5-flash`，替換為 `gemini-flash-latest`，
並補充說明：「使用長效別名，Google 自動管理版本升級」。

### 驗收標準

- [ ] README 中 `gemini-2.5-flash` 全數更新為 `gemini-flash-latest`
- [ ] rev1/rev2 對照表保留歷史記錄（標注「舊版設定」）

---

## 進度追蹤

| # | 任務 | Priority | Status |
|---|------|----------|--------|
| 1 | save_message 非同步化 | 🔴 P1 | `[x] DONE` |
| 2 | GAS catch error 變數 Bug | 🔴 P2 | `[x] DONE` |
| 3 | 歷史對話角色判斷修正 | 🔴 P3 | `[x] DONE` |
| 4 | 圖片路徑並發覆蓋問題 | 🟡 P4 | `[x] DONE` |
| 5 | README 模型版本一致性 | 🟢 P5 | `[x] DONE` |

## 來源 reference
Resume: agy --conversation=bb45afc3-225e-47f6-8114-fa5969e4b304 (or -c)
