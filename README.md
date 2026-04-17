# LINEBOT rev2.1

> 整合 Google Gemini 的 LINE 聊天機器人（使用新版 google-genai SDK）

## 版本資訊

- **版本**: rev2.1
- **更新日期**: 2026-04-17
- **重大更新**: 更新 Gemini 模型為長效別名 `gemini-flash-latest` 以確保穩定服務

## 更新紀錄

### rev2.1 (2026-04-17)
- ✅ 更新 Gemini 模型為長效別名 `gemini-flash-latest`。
- ✅ 確保模型退役時系統能自動過渡，無需手動修改。

### rev2 (2025-12-25)
- ✅ 改用新版 `google-genai` SDK
- ✅ 統一使用 `gemini-2.5-flash` 模型 (支援文字與圖片)
- ✅ 使用 `genai.Client()` 取代 `genai.configure()`
- ✅ 使用 `client.chats.create()` 支援多輪對話
- ✅ 移除已棄用的 `google-generativeai` 套件

### rev1 (2025-12-25)
- 初始模組化重構版本

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
│   └── bookmark.py           # 書籤與歷史紀錄服務
│
├── utils/                    # 工具模組
│   ├── __init__.py
│   └── keepalive.py          # 背景保活任務
│
├── pic/                      # 圖片資源
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
    model='gemini-2.5-flash',
    contents=prompt
)
```

## 功能說明

### 1. AI 文字對話 (`services/ai_text.py`)
- 使用 `ai:` 前綴觸發
- 使用 `client.chats.create()` 支援歷史對話
- 自動轉換 Google Sheet 歷史格式為 SDK Content 格式

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
- 使用 `gemini-2.5-flash` 模型 (支援多模態)
- 支援 PIL.Image 直接傳入或 bytes 方式

```python
from services import analyze_image

result = analyze_image("path/to/image.jpg")
result = analyze_image("path/to/image.jpg", prompt="這張圖裡有什麼動物？")
```

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

## 注意事項

1. **SDK 版本**: 本專案使用 `google-genai`，請確保不要同時安裝 `google-generativeai`
2. **模型**: 統一使用 `gemini-2.5-flash`，此模型同時支援文字與圖片
3. **API 金鑰**: 請勿將 `.env` 推送到版本控制
4. **棄用警告**: `google-generativeai` 將於 2025/11/30 停止更新

## 與 rev1 差異

| 項目 | rev1 | rev2 |
|------|------|------|
| SDK | `google-generativeai` (舊版) | `google-genai` (新版) |
| 初始化 | `genai.configure()` | `genai.Client()` |
| 文字生成 | `model.generate_content()` | `client.models.generate_content()` |
| 聊天 | `model.start_chat()` | `client.chats.create()` |
| 文字模型 | `gemini-2.5-flash` | `gemini-2.5-flash` |
| 圖片模型 | `gemini-2.0-flash-exp` | `gemini-2.5-flash` (統一) |

---

更新日期：2025-12-25
