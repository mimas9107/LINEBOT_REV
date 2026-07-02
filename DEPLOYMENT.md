---
name:          "DEPLOYMENT.md"
description:   "Complete deployment guide for LINEBOT rev2.1"
created_date:  "2026/07/02"
modified_date: "2026/07/02"
project_version: "2.1.0"
document_version: "1.0.0"
agent_sign: ['gemini cli/current_agent']
---

# LINEBOT rev2.1 完整部署指南

> 本文檔說明如何從零開始部署 LINEBOT rev2.1，包含 Google Sheets/GAS 設定與 Render.com 部署。

---

## 目錄

1. [前置需求](#1-前置需求)
2. [第一部分：Google Sheets 與 GAS 設定](#2-google-sheets--gas-設定)
3. [第二部分：LINE Developers 設定](#3-line-developers-設定)
4. [第三部分：Python 專案部署](#4-python-專案部署)
5. [第四部分：Render.com 部署](#5-rendercom-部署)
6. [驗證與除錯](#6-驗證與除錯)

---

## 1. 前置需求

| 項目 | 說明 |
|------|------|
| Google 帳號 | 用於建立 Google Sheets 與 GAS |
| LINE Developer 帳號 | 用於建立 LINE Bot |
| Gemini API Key | 用於 AI 對話功能 |
| Render.com 帳號 | 用於部署 Python 服務 |
| Git | 用於版本控制 |

---

## 2. Google Sheets 與 GAS 設定

這部分是訊息持久化與歷史對話的儲存後端。

### 步驟 2.1：建立 Google Sheets

1. 前往 [Google Sheets](https://sheets.new/) 建立一份新試算表
2. 命名為「LINEBOT 訊息紀錄」（或你喜歡的名稱）
3. 建立以下三個工作表（Sheet）：

#### 工作表 1：「LINE訊息紀錄」

- 點擊底部 `+` 新增工作表
- 命名為 `LINE訊息紀錄`
- 在第一列輸入標題：

| A | B | C | D | E |
|---|---|---|---|---|
| 時間戳記 | 使用者 ID | 訊息類型 | 訊息內容 | 書籤狀態 |

- 欄位說明：
  - **A 欄**：訊息時間（系統自動填入）
  - **B 欄**：使用者 ID（LINE 使用者 ID）
  - **C 欄**：訊息類型（text / image）
  - **D 欄**：訊息內容
  - **E 欄**：書籤狀態（保留，用於書籤功能）

#### 工作表 2：「default」

- 新增另一個工作表，命名為 `default`
- 填入以下設定：

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | 設定名稱 | 值 | | 目的工作表 | Gemini AI 開關 |
| 2 | | | | LINE訊息紀錄 | Y |

- **D2**：目的工作表名稱，預設為 `LINE訊息紀錄`
- **E2**：Gemini AI 開關
  - `Y` = 正常模式（處理訊息 + 書籤判斷）
  - `N` = 僅記錄模式（只儲存訊息，不做書籤判斷）

#### 工作表 3：「keepalive」

- 新增另一個工作表，命名為 `keepalive`
- 第一列輸入標題：

| A | B | C | D |
|---|---|---|---|
| 時間戳記 | 執行函式 | 狀態 | 其他備註 |

- 此工作表會由保活任務自動建立，但你也可以手動建立以確保存在

### 步驟 2.2：部署 GAS Web App

1. 在試算表中，點擊上方選單 **擴充功能** > **Apps Script**
2. 這會開啟 Apps Script 編輯器
3. 刪除預設的 `Code.gs` 內容
4. 將專案中 `google_app_script/` 目錄下的 **所有 `.gs` 檔案內容合併到一個檔案** 中

#### 合併步驟（重要）：

Apps Script 編輯器只能有一個 `Code.gs` 檔案。你需要將以下檔案的內容依序複製到 `Code.gs`：

1. `linebot.gs`（主要入口，複製全部）
2. `main.gs`（工作表管理，複製全部）
3. `BookMark.gs`（書籤功能，複製全部）
4. `UrlHandler.gs`（網址處理，複製全部）
5. `AI.gs`（AI 標籤分析，複製全部）

> **提示**：複製時，每個檔案之間用空行分隔即可。順序不重要，只要全部貼進去 `Code.gs`。

#### 最後一步：

在 `Code.gs` 最上方確認有這個函式（從 `linebot.gs`）：

```javascript
function doPost(e) {
  // ... 所有程式碼都在這裡
}
```

如果有多個 `function doPost(e)` 定義（不可能，只有一個），確保只保留一個。

### 步驟 2.3：發布為 Web App

1. 在 Apps Script 編輯器中，點擊右上角 **部署** > **新增部署專案**
2. 點擊 **選擇類型** > **Web 應用程式**
3. 設定如下：

| 欄位 | 值 |
|------|-----|
| 說明 | LINEBOT GAS Web App v1 |
| 執行身分 | **我**（你的 Google 帳號） |
| 誰可以存取 | **任何人** |

4. 點擊 **部署**
5. 授權應用程式存取你的 Google 資料：
   - 出現授權視窗時，選擇你的 Google 帳號
   - 點擊 **進階** > **前往 LINEBOT...（不安全）**
   - 點擊 **允許**
6. 複製生成的 **Web 應用程式 URL**，格式類似：
   ```
   https://script.google.com/macros/s/AKfycbxXXXXXXXXXXXXXXX/exec
   ```
7. **這個 URL 稍後會用到**，先記下來

---

## 3. LINE Developers 設定

### 步驟 3.1：建立 Messaging API Channel

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 登入你的 LINE 帳號
3. 點擊 **建立** > 選擇 **Messaging API Channel**
4. 填寫：
   - **Logo**：上傳你的 Bot 頭像
   - **Channel name**：你的 Bot 名稱
   - **Channel description**：Bot 說明
   - **Start selling**：選擇 **On**（如果需要）
5. 點擊 **Create**

### 步驟 3.2：取得 Channel 憑證

1. 進入剛建立的 Channel 頁面
2. 在 **Channel settings** 分頁下：
   - **Channel secret**：點擊 **重新發行**（Reissue）取得新的 Secret
   - **Channel access token**：點擊 **發行**（Issue）取得 Token
3. 記下以下三個值：
   - `LINE_CHANNEL_SECRET`（Channel secret）
   - `LINE_CHANNEL_ACCESS_TOKEN`（Channel access token）

### 步驟 3.3：設定 Webhook URL

1. 在 **Messaging API** 分頁下：
   - 勾選 **使用 Webhook**（Use webhook）
   - **Webhook URL**：暫時留空，等部署完成後再設定
2. 在 **Bot settings** 分頁：
   - **親暱名稱**：設定 Bot 顯示名稱
   - **Emoji**：選擇表情符號
   - **Greeting message**：設定歡迎訊息（可選）
   - **Disable auto语译**：根據需要設定

### 步驟 3.4：測試使用者

1. 掃描 QR Code（在 Channel 頁面的 **Test bot** 區域）
2. 這會邀請你加入測試群組，你可以在 LINE 中與 Bot 對話測試

---

## 4. Python 專案部署

### 步驟 4.1：取得專案程式碼

```bash
git clone <your-repo-url>
cd LINEBOT_REV
```

### 步驟 4.2：建立環境變數

1. 複製範例環境變數檔：
   ```bash
   cp .env.example .env
   ```
   > 如果沒有 `.env.example`，直接建立 `.env` 檔案即可。

2. 編輯 `.env` 檔案，填入你的憑證：

```env
# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN=你的LINE_Channel_Access_Token
LINE_CHANNEL_SECRET=你的LINE_Channel_Secret

# Gemini AI 設定
GEMINI_API_KEY=你的Gemini_API_Key

# Google Apps Script 設定
GOOGLE_APPS_SCRIPT_URL=你在步驟2.3取得的Web App URL

# 可選：自訂設定
# CHAT_HISTORY_LENGTH=5          # 歷史對話保留筆數
# KEEPALIVE_INTERVAL=780         # 保活間隔（秒）
# SELF_URL=https://your-domain.onrender.com/about  # 你的部署域名
```

### 步驟 4.3：安裝相依套件

```bash
pip install -r requirements.txt
```

### 步驟 4.4：本機測試

```bash
python app.py
```

應該會看到：
```
[Keepalive] Started
 * Running on http://127.0.0.1:5000
```

### 步驟 4.5：設定 LINE Webhook URL

1. 回到 [LINE Developers Console](https://developers.line.biz/console/)
2. 進入你的 Channel 設定
3. 在 **Messaging API** 分頁，將 **Webhook URL** 設為：
   ```
   https://your-domain.onrender.com/callback
   ```
   > 如果在本機測試，先用 ngrok 等工具暴露本地端口：
   > ```bash
   > ngrok http 5000
   > ```
   > 然後將 ngrok 提供的 URL 設為 Webhook URL

4. 點擊 **重新發行**（Verify）測試 Webhook 是否正常

---

## 5. Render.com 部署

### 步驟 5.1：準備 Git 倉庫

```bash
git init
git add .
git commit -m "Initial LINEBOT rev2.1 deployment"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 步驟 5.2：建立 Render 服務

1. 前往 [Render.com](https://render.com/) 並登入
2. 點擊 **New** > **Web Service**
3. 連接你的 Git 倉庫（GitHub / GitLab / Bitbucket）
4. 填寫設定：

| 欄位 | 值 |
|------|-----|
| Name | linebot-rev2 |
| Region | 選擇離台灣最近的（如 Tokyo） |
| Branch | main（或你的分支） |
| Root Directory | 留空（如果在子目錄則填 `LINEBOT_REV`） |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | Free（免費方案）或 Starter |

### 步驟 5.3：設定環境變數

在 Render Dashboard 的 **Environment** 分頁，新增以下環境變數：

| Key | Value |
|-----|-------|
| LINE_CHANNEL_ACCESS_TOKEN | 你的 LINE Token |
| LINE_CHANNEL_SECRET | 你的 LINE Secret |
| GEMINI_API_KEY | 你的 Gemini API Key |
| GOOGLE_APPS_SCRIPT_URL | 你的 GAS Web App URL |

> **重要**：不要將 `.env` 檔案提交到 Git，Render 使用環境變數而非 `.env` 檔案。

### 步驟 5.4：設定自訂網域（可選）

1. 在 **Custom Domains** 分頁添加你自己的網域
2. 按照指示設定 DNS 記錄

### 步驟 5.5：部署

1. 點擊 **Create Web Service**
2. Render 會自動從 Git 拉取程式碼並部署
3. 等待約 1-2 分鐘，狀態變為 **Live** 即完成

### 步驟 5.6：設定 LINE Webhook

1. 獲取 Render 提供的 URL，例如：
   ```
   https://linebot-rev2.onrender.com
   ```
2. 回到 LINE Developers Console
3. 將 **Webhook URL** 設為：
   ```
   https://linebot-rev2.onrender.com/callback
   ```
4. 點擊 **Verify**

---

## 6. 驗證與除錯

### 6.1 基本功能測試

在 LINE 中與 Bot 對話測試以下功能：

| 測試項目 | 操作 | 預期結果 |
|----------|------|----------|
| 基本回應 | 發送一般文字 | Bot 不回覆（非 ai: 前綴） |
| AI 對話 | 發送 `ai: 你好` | Bot 回覆 AI 生成的內容 |
| 複製模式 | 發送 `c: 測試` | Bot 回覆 `測試` |
| 圖片辨識 | 發送一張圖片 | Bot 回覆 AI 圖片分析結果 |
| 多輪對話 | 連續發送 `ai:` 訊息 | Bot 能記住之前內容 |

### 6.2 檢查 Google Sheets

1. 打開你的 Google Sheets
2. 確認 **LINE訊息紀錄** 工作表中有新增的訊息列
3. 確認 **keepalive** 工作表中有保活記錄

### 6.3 Render 日誌除錯

如果 Bot 沒有回應：

1. 前往 Render Dashboard
2. 點擊你的服務 > **Logging** 分頁
3. 查看是否有錯誤訊息

常見錯誤：

| 錯誤訊息 | 原因 | 解決方法 |
|----------|------|----------|
| `Missing configurations` | 環境變數未設定 | 檢查 Render 的 Environment 設定 |
| `401 Unauthorized` | LINE Token 錯誤 | 重新發行 LINE Channel access token |
| `Connection refused` | GAS URL 錯誤 | 檢查 GOOGLE_APPS_SCRIPT_URL 是否正確 |
| `API key not valid` | Gemini API Key 錯誤 | 檢查 GEMINI_API_KEY 是否正確 |

### 6.4 保活機制確認

Render 免費方案會在 15 分鐘無流量時休眠。本專案內建保活機制：

- 每 **13 分鐘**（可透過 `KEEPALIVE_INTERVAL` 調整）自動 ping 自己
- 同時會記錄一條 keepalive log 到 Google Sheets
- 可以在 Sheets 的 **keepalive** 工作表查看保活是否運作

### 6.5 緊急重啟

如果 Bot 沒有回應且日誌顯示異常：

1. 前往 Render Dashboard
2. 點擊 **Manual Restart**
3. 等待約 30 秒後重新測試

---

## 附錄：專案結構

```
LINEBOT_REV/
├── app.py                    # Flask 應用程式入口
├── config.py                 # 統一設定管理
├── requirements.txt          # Python 相依套件
├── .env                      # 環境變數（不提交到 Git）
├── .env.example              # 環境變數範本
│
├── handlers/
│   ├── __init__.py
│   └── line_handler.py       # LINE Webhook 事件處理
│
├── services/
│   ├── __init__.py
│   ├── ai_text.py            # Gemini 文字對話
│   ├── ai_image.py           # Gemini 圖片辨識
│   └── bookmark.py           # 書籤與歷史紀錄服務
│
├── utils/
│   ├── __init__.py
│   └── keepalive.py          # 背景保活任務
│
├── pic/                      # 圖片暫存目錄
│
└── google_app_script/        # GAS 腳本（合併後部署到 Google）
    ├── linebot.gs            # 主要入口
    ├── main.gs               # 工作表管理
    ├── BookMark.gs           # 書籤功能
    ├── UrlHandler.gs         # 網址處理
    └── AI.gs                 # AI 標籤分析
```

## 附錄：GAS 檔案合併說明

由於 Apps Script 編輯器只接受單一 `Code.gs` 檔案，部署時需要將以下檔案合併：

```
合併順序（建議）：
1. linebot.gs       → 完整複製到 Code.gs
2. main.gs          → 追加到 Code.gs
3. BookMark.gs      → 追加到 Code.gs
4. UrlHandler.gs    → 追加到 Code.gs
5. AI.gs            → 追加到 Code.gs
```

每個檔案之間用空行分隔即可。合併完成後在 Apps Script 編輯器中按 `Ctrl+S` 儲存。
