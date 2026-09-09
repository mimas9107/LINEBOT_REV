---
name:          "README.md"
description:   "Main documentation for LINEBOT rev2.4.1"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/10 00:25:00"
project_version: "2.4.1"
document_version: "1.3.2"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent', 'opencode/current_agent']
---

# LINEBOT

> 整合 Google Gemini 的 LINE 聊天機器人（使用新版 google-genai SDK）

## 版本資訊

- **版本**: 2.4.1
- **更新日期**: 2026-09-10
- **當前重點**: 插件化架構（ENABLED_PLUGINS 白名單）+ 天氣功能（CWA 降雨機率/GPS 天氣、TDX CCTV、路線規劃）、Gemini Function Calling 三上限保護；修正 tools 須為 SDK Tool 物件（dict 直傳會被 Pydantic 拒收）

> 完整版本變更紀錄請見 [`CHANGELOG.md`](./CHANGELOG.md)。

## 專案結構

```
linebot-rev2/
├── app.py                    # Flask 應用程式入口
├── config.py                 # 統一設定管理
├── requirements.txt          # 相依套件
├── .gitignore
├── README.md                 # 本文件
│
├── handlers/                 # 事件處理器
│   ├── __init__.py
│   └── line_handler.py       # LINE Webhook 事件處理
│
├── services/                 # 服務模組
│   ├── __init__.py
│   ├── ai_text.py            # Gemini 文字對話 (使用 google-genai)
│   ├── ai_image.py           # Gemini 圖片辨識 (使用 google-genai)
│   ├── bookmark.py           # Google Sheet 書籤與備援歷史紀錄服務
│   ├── database.py           # SQLite 連線、初始化與統計
│   ├── weather_tools.py      # 天氣查詢 handler（CWA/TDX，供插件呼叫）
│   ├── plugins/              # Gemini Function Calling 插件
│   │   ├── __init__.py       # 插件掃描、白名單、Registry 完整性檢查
│   │   └── weather.py        # 天氣插件（4 支 tool schema + handler）
│   └── chat_history.py       # SQLite 對話歷史服務
│
├── utils/                    # 工具模組
│   ├── __init__.py
│   └── keepalive.py          # 背景保活任務
│
├── tools/                    # 開發輔助工具
│   └── check_models.py       # 查詢目前 API Key 可用 Gemini 模型
│
├── data/                     # SQLite runtime database 目錄 (.db 不進 Git)
├── pic/                      # 圖片暫存資源
├── DEPLOYMENT.md             # 完整部署指南
└── google_app_script/        # Google Apps Script 腳本
```

## SDK 變更說明

### 舊版 (已棄用)
```python
# ❌ 不要再使用
import google.generativeai as genai
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
response = model.generate_content(prompt)
```

### 新版 (本專案使用)
```python
# ✅ 正確用法
from google import genai

client = genai.Client(api_key=API_KEY)
response = client.models.generate_content(
    model='gemini-flash-latest',  # 使用長效別名，Google 自動管理版本升級
    contents=prompt
)
```

## 功能說明

### 1. AI 文字對話 (`services/ai_text.py`)
- 使用 `ai:` 前綴觸發
- 使用 SQLite 對話歷史組合 prompt
- SQLite 不可用時 fallback 到 Google Sheet 歷史

```python
from services import chat_with_ai

# 單次對話
response = chat_with_ai("你好，請介紹台北美食")

# 帶歷史對話
history = [
    {"userId": "U123", "messageText": "你好"},
    {"userId": "bot", "messageText": "你好！有什麼可以幫你的？"}
]
response = chat_with_ai("推薦我小吃", history=history)
```

### 2. AI 圖片辨識 (`services/ai_image.py`)
- 使用者上傳圖片自動觸發
- 使用 `gemini-flash-latest` 模型 (支援多模態，長效別名)
- 支援 PIL.Image 直接傳入或 bytes 方式

```python
from services import analyze_image

result = analyze_image("path/to/image.jpg")
result = analyze_image("path/to/image.jpg", prompt="這張圖裡有什麼動物？")
```

### 3. 書籤功能 (`services/bookmark.py`)
- 與 Google Apps Script 互動
- 儲存訊息到 Google Sheet
- 作為外部紀錄與 SQLite 歷史讀取失敗時的 fallback

### 4. SQLite 對話歷史 (`services/database.py`, `services/chat_history.py`)
- 儲存使用者訊息與 AI 回覆
- 支援依使用者查詢歷史
- runtime database 預設位於 `data/chat_history.db`
- `.gitignore` 已排除 `data/*.db` 與 WAL/SHM runtime 檔案

### 5. Database API (`app.py`)
- 需設定 `API_SECRET_KEY`
- 支援下載、統計、匯出與查詢 SQLite 對話資料
- `POST /api/db/restore` 與 `POST /api/db/validate` 已停用，避免 Render 實例因上傳還原流程當機

### 6. 保活機制 (`utils/keepalive.py`)
- 防止 Render.com 免費方案休眠
- 每 13 分鐘隨機執行保活任務

## 環境變數

在 `.env` 檔案中設定：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_TOKEN
LINE_CHANNEL_SECRET=你的_LINE_SECRET
GEMINI_API_KEY=你的_GEMINI_KEY
GEMINI_MODEL=gemini-flash-latest
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/XXXX/exec
CHAT_HISTORY_LENGTH=5
DOWNLOAD_IMAGE_DIR=pic
KEEPALIVE_INTERVAL=780
SELF_URL=https://your-render-domain.onrender.com/about
DATABASE_PATH=data/chat_history.db
API_SECRET_KEY=請改成高強度隨機字串
```

## 安裝與執行

### 本機開發

```bash
# 安裝相依套件
pip install -r requirements.txt

# 建立 .env 設定檔
cp .env.example .env
# 編輯 .env 填入實際值

# 啟動開發伺服器
python app.py
```

### 部署到 Render.com

```bash
# 使用 gunicorn 啟動
gunicorn app:app
```

## 注意事項
 
1. **SDK 版本**: 本專案使用 `google-genai`，請確保不要同時安裝 `google-generativeai`
2. **模型**: 統一使用 `gemini-flash-latest` (長效別名，Google 自動管理版本升級)
3. **API 金鑰**: 請勿將 `.env` 推送到版本控制
4. **Database API**: Render 必須設定 `API_SECRET_KEY` 才能使用 `/api/db/*`
5. **Database 上傳**: `/api/db/restore` 與 `/api/db/validate` 目前固定停用
6. **棄用警告**: `google-generativeai` 將於 2025/11/30 停止更新
7. **503 容錯**: 文字對話依 `config.MODEL_LIST` 依序 fallback；markfail 模型失敗後冷卻 600 秒。AI 失敗時不寫入對話歷史

## 與 rev1 差異

| 項目 | rev1 | rev2 |
|------|------|------|
| SDK | `google-generativeai` (舊版) | `google-genai` (新版) |
| 初始化 | `genai.configure()` | `genai.Client()` |
| 文字生成 | `model.generate_content()` | `client.models.generate_content()` |
| 聊天 | `model.start_chat()` | `client.chats.create()` |
| 文字模型 | `gemini-2.5-flash` | `gemini-flash-latest` (長效別名) |
| 圖片模型 | `gemini-2.0-flash-exp` | `gemini-flash-latest` (統一，長效別名) |
