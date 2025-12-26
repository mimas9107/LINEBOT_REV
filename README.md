# LINEBOT rev3

> 整合 Google Gemini 的 LINE 聊天機器人（SQLite 對話記錄版）

## 版本資訊

- **版本**: rev3
- **更新日期**: 2025-12-25
- **重大更新**: 新增 SQLite 對話歷史記錄系統，同時記錄 User 和 AI 訊息

## 更新紀錄

### rev3 (2025-12-25)
- ✅ 新增 SQLite 對話歷史記錄系統
- ✅ 同時記錄使用者訊息與 AI 回應
- ✅ 新增資料庫下載/匯出 API
- ✅ 新增本地端資料庫解析工具 `tools/db_analyzer.py`
- ✅ 保留 Google Sheet 書籤功能

### rev2 (2025-12-25)
- 改用 `google-genai` SDK

### rev1 (2025-12-25)
- 初始模組化重構版本

## 專案結構

```
linebot-rev3/
├── app.py                    # Flask 應用程式入口 (含資料庫 API)
├── config.py                 # 統一設定管理
├── requirements.txt
├── .gitignore
├── README.md
│
├── handlers/
│   └── line_handler.py       # LINE 事件處理 (含訊息記錄)
│
├── services/
│   ├── database.py           # 【新增】SQLite 資料庫服務
│   ├── chat_history.py       # 【新增】對話歷史服務
│   ├── ai_text.py            # Gemini 文字對話
│   ├── ai_image.py           # Gemini 圖片辨識
│   └── bookmark.py           # 書籤服務 (Google Sheet)
│
├── utils/
│   └── keepalive.py          # 背景保活任務
│
├── tools/                    # 【新增】本地端工具
│   └── db_analyzer.py        # 資料庫解析工具
│
├── data/                     # 【新增】資料目錄 (自動建立)
│   └── chat_history.db       # SQLite 資料庫
│
├── pic/
└── google_app_script/
```

## 對話記錄流程

```
User 傳送 "ai: 你好"
    │
    ├─→ 儲存到 SQLite (role: user)
    │
    ├─→ 從 SQLite 取得歷史對話
    │
    ├─→ 組合 prompt，呼叫 Gemini
    │
    ├─→ 儲存 AI 回應到 SQLite (role: model)
    │
    └─→ 回覆使用者
```

## 資料庫結構

### chat_messages 表

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | INTEGER | 自動遞增主鍵 |
| user_id | TEXT | LINE 使用者 ID |
| role | TEXT | 'user' 或 'model' |
| message_type | TEXT | 訊息類型 (text, image) |
| message_text | TEXT | 訊息內容 |
| created_at | TIMESTAMP | 建立時間 |

## API 端點

### 基本端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | 首頁 |
| `/about` | GET | 關於頁面 |
| `/health` | GET | 健康檢查 (含資料庫統計) |
| `/callback` | POST | LINE Webhook |

### 資料庫管理 API（需要 API Key）

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/db/download` | GET | 下載 SQLite 資料庫檔案 |
| `/api/db/stats` | GET | 取得資料庫統計 |
| `/api/db/export` | GET | 匯出為 JSON |
| `/api/db/messages` | GET | 查詢訊息列表 |
| `/api/db/users` | GET | 取得使用者列表 |
| `/api/db/user/<id>/history` | GET | 取得特定使用者對話歷史 |

### API 驗證

所有 `/api/db/*` 端點都需要 API Key 驗證：

```bash
# 方式 1: Header
curl -H "X-API-Key: YOUR_SECRET_KEY" https://your-app.onrender.com/api/db/stats

# 方式 2: Query Parameter
curl "https://your-app.onrender.com/api/db/stats?api_key=YOUR_SECRET_KEY"
```

## 本地端工具使用

### 安裝

```bash
pip install requests  # 如果要使用下載功能
```

### 使用範例

```bash
cd tools/

# 從 Render.com 下載資料庫
python db_analyzer.py download \
  --url https://your-app.onrender.com \
  --api-key YOUR_SECRET_KEY \
  --output chat_history.db

# 查看統計資訊
python db_analyzer.py stats --db chat_history.db

# 列出所有使用者
python db_analyzer.py users --db chat_history.db

# 查看特定使用者的對話
python db_analyzer.py history --db chat_history.db --user U1234567890abcdef

# 匯出為 JSON
python db_analyzer.py export --db chat_history.db --format json --output export.json

# 匯出為 CSV
python db_analyzer.py export --db chat_history.db --format csv --output export.csv

# 匯出特定使用者對話為文字檔
python db_analyzer.py export --db chat_history.db --format txt --user U1234567890abcdef
```

## 環境變數

```env
# LINE Bot
LINE_CHANNEL_ACCESS_TOKEN=xxx
LINE_CHANNEL_SECRET=xxx

# Gemini
GEMINI_API_KEY=xxx

# Google Apps Script (書籤功能)
GOOGLE_APPS_SCRIPT_URL=xxx

# API 安全金鑰 (重要！請設定複雜的密鑰)
API_SECRET_KEY=your-very-secure-secret-key
```

## 部署注意事項

1. **API_SECRET_KEY**: 請務必設定一個複雜的密鑰，用於保護資料庫 API
2. **資料持久化**: Render.com 免費方案的檔案系統會在重啟時清除，建議：
   - 定期下載資料庫備份
   - 或升級到付費方案使用持久化儲存
3. **資料庫路徑**: 預設為 `data/chat_history.db`，目錄會自動建立

## 與 rev2 差異

| 項目 | rev2 | rev3 |
|------|------|------|
| 對話記錄 | Google Sheet (僅 User) | SQLite (User + AI) |
| 歷史查詢 | 呼叫 Google Apps Script | 本地 SQL 查詢 |
| 查詢效率 | 慢 | 快 (有索引) |
| 資料下載 | 無 | 提供 API |
| 本地工具 | 無 | db_analyzer.py |
| 書籤功能 | Google Sheet | 保留 Google Sheet |

---

更新日期：2025-12-25
