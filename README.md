# LINEBOT rev1

> 整合 Google Gemini 的 LINE 聊天機器人（重構版）

## 版本資訊

- **版本**: rev1
- **重構日期**: 2025-12-25
- **基於**: 原始 LINEBOT 專案

## 專案結構

```
linebot-rev1/
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
│   ├── ai_text.py            # Gemini 文字對話服務
│   ├── ai_image.py           # Gemini 圖片辨識服務
│   └── bookmark.py           # 書籤與歷史紀錄服務
│
├── utils/                    # 工具模組
│   ├── __init__.py
│   └── keepalive.py          # 背景保活任務
│
├── pic/                      # 圖片資源
└── google_app_script/        # Google Apps Script 腳本
```

## 功能說明

### 1. AI 文字對話 (`services/ai_text.py`)
- 使用 `ai:` 前綴觸發
- 整合 Google Gemini API
- 支援歷史對話記憶（從 Google Sheet 取得）

### 2. AI 圖片辨識 (`services/ai_image.py`)
- 使用者上傳圖片自動觸發
- 使用 Gemini Vision 模型分析
- 備用支援本地 LMStudio

### 3. 書籤功能 (`services/bookmark.py`)
- 與 Google Apps Script 互動
- 儲存訊息到 Google Sheet
- 取得歷史對話記錄

### 4. 保活機制 (`utils/keepalive.py`)
- 防止 Render.com 免費方案休眠
- 每 13 分鐘隨機執行保活任務

## 環境變數

在 `.env` 檔案中設定：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_TOKEN
LINE_CHANNEL_SECRET=你的_LINE_SECRET
GEMINI_API_KEY=你的_GEMINI_KEY
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/XXXX/exec
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

## 模組使用範例

### AI 文字對話

```python
from services import chat_with_ai

response = chat_with_ai("你好，請介紹台北的美食")
print(response)
```

### AI 圖片辨識

```python
from services import analyze_image

result = analyze_image("path/to/image.jpg")
print(result)
```

### 書籤服務

```python
from services import get_chat_history, save_message

# 取得歷史對話
history = get_chat_history(user_id="U1234567890")

# 儲存訊息
save_message(
    timestamp=1234567890,
    user_id="U1234567890",
    message_type="text",
    message_text="Hello"
)
```

## 與原版差異

| 項目 | 原版 | rev1 |
|------|------|------|
| 程式碼結構 | 單一 app.py (~280 行) | 模組化拆分 |
| 設定管理 | 散落各處 | 統一 config.py |
| AI 文字 | 內嵌於主程式 | services/ai_text.py |
| AI 圖片 | 內嵌於主程式 | services/ai_image.py |
| 書籤功能 | 內嵌於主程式 | services/bookmark.py |
| 保活任務 | 內嵌於主程式 | utils/keepalive.py |
| 可測試性 | 較困難 | 模組化易於測試 |

## 注意事項

1. **Gemini 模型版本**: 目前使用 `gemini-2.5-flash` (文字) 和 `gemini-2.0-flash-exp` (圖片)，可在 `config.py` 中調整
2. **API 金鑰**: 請勿將 `.env` 推送到版本控制
3. **Google Apps Script**: 需要另外部署 `google_app_script/` 目錄中的腳本

---

重構完成日期：2025-12-25
