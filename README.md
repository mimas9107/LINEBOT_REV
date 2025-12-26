# LINEBOT rev3.1

> 整合 Google Gemini 的 LINE 聊天機器人（支援資料庫備份還原）

## 版本資訊

- **版本**: rev3.1
- **更新日期**: 2025-12-26
- **重大更新**: 新增資料庫 Restore 功能，支援備份還原

---

## 🆕 rev3.1 新功能

### 1. 資料庫還原 (Restore)

解決 Render.com 免費方案重啟後 SQLite 資料消失的問題。

**還原流程：**
```
1. Maintenance mode 啟動（停止接收新訊息）
2. 等待 2 秒（讓進行中請求完成）
3. 驗證上傳的 SQLite 檔案
4. 備份現有資料庫
5. 原子替換（os.replace）
6. WAL checkpoint + VACUUM
7. 解除 Maintenance mode
8. 若失敗自動 Rollback
```

### 2. Maintenance Mode

- 還原期間自動啟用
- LINE 訊息會收到「系統維護中」回覆
- 訊息不會被處理（捨棄）

### 3. 新增 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/db/restore` | POST | 上傳 DB 檔案還原 |
| `/api/db/validate` | POST | 驗證 DB 檔案（不還原） |
| `/api/db/maintenance` | GET | 查詢維護模式狀態 |

---

## 📋 備份還原流程

### 標準操作流程

```bash
# 1. 定期備份（建議每天一次）
python tools/db_analyzer.py download \
  --url https://your-app.onrender.com \
  --api-key YOUR_KEY \
  --output backup_$(date +%Y%m%d).db

# 2. Render 重啟後還原
python tools/db_analyzer.py restore \
  --url https://your-app.onrender.com \
  --api-key YOUR_KEY \
  --file backup_20251226.db

# 3. 驗證還原結果
python tools/db_analyzer.py remote-stats \
  --url https://your-app.onrender.com \
  --api-key YOUR_KEY
```

### 還原前驗證（可選）

```bash
# 僅驗證檔案，不實際還原
python tools/db_analyzer.py validate \
  --url https://your-app.onrender.com \
  --api-key YOUR_KEY \
  --file backup.db
```

### 檢查維護模式狀態

```bash
python tools/db_analyzer.py maintenance \
  --url https://your-app.onrender.com \
  --api-key YOUR_KEY
```

---

## 🛠 db_analyzer.py 完整指令

### 遠端操作

```bash
# 下載資料庫
python db_analyzer.py download --url URL --api-key KEY [--output FILE]

# 還原資料庫
python db_analyzer.py restore --url URL --api-key KEY --file FILE

# 驗證檔案（不還原）
python db_analyzer.py validate --url URL --api-key KEY --file FILE

# 查看遠端統計
python db_analyzer.py remote-stats --url URL --api-key KEY

# 查看維護模式
python db_analyzer.py maintenance --url URL --api-key KEY
```

### 本地操作

```bash
# 查看統計
python db_analyzer.py stats --db FILE

# 列出使用者
python db_analyzer.py users --db FILE

# 查看對話
python db_analyzer.py history --db FILE --user USER_ID [--limit N]

# 匯出 JSON
python db_analyzer.py export --db FILE --format json [--output FILE]

# 匯出 CSV
python db_analyzer.py export --db FILE --format csv [--output FILE]

# 匯出對話文字檔
python db_analyzer.py export --db FILE --format txt --user USER_ID
```

---

## 📁 專案結構

```
linebot-rev3.1/
├── app.py                    # Flask 應用（含 restore API）
├── config.py                 # 設定管理
├── requirements.txt
│
├── handlers/
│   └── line_handler.py       # LINE 事件處理（含 maintenance 檢查）
│
├── services/
│   ├── database.py           # SQLite 服務（含 restore/maintenance）
│   ├── chat_history.py       # 對話歷史
│   ├── ai_text.py            # Gemini 文字
│   ├── ai_image.py           # Gemini 圖片
│   └── bookmark.py           # 書籤功能
│
├── utils/
│   └── keepalive.py          # 保活任務
│
├── tools/
│   └── db_analyzer.py        # 資料庫工具（含 restore 指令）
│
└── data/
    └── chat_history.db       # SQLite 資料庫
```

---

## 📡 API 端點總覽

### 基本端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | 首頁（顯示運作狀態） |
| `/about` | GET | 關於頁面 |
| `/health` | GET | 健康檢查 |
| `/callback` | POST | LINE Webhook |

### 資料庫管理 API（需 API Key）

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/db/download` | GET | 下載 SQLite 檔案 |
| `/api/db/stats` | GET | 統計資訊 |
| `/api/db/export` | GET | 匯出 JSON |
| `/api/db/messages` | GET | 查詢訊息 |
| `/api/db/users` | GET | 使用者列表 |
| `/api/db/restore` | POST | **還原資料庫** |
| `/api/db/validate` | POST | **驗證 DB 檔案** |
| `/api/db/maintenance` | GET | **維護模式狀態** |

---

## ⚙️ 環境變數

```env
# LINE Bot
LINE_CHANNEL_ACCESS_TOKEN=xxx
LINE_CHANNEL_SECRET=xxx

# Gemini
GEMINI_API_KEY=xxx

# Google Apps Script (書籤)
GOOGLE_APPS_SCRIPT_URL=xxx

# API 安全金鑰
API_SECRET_KEY=your-secret-key
```

---

## ⚠️ 注意事項

### Render.com 免費方案限制

- 檔案系統**非持久化**，重啟後消失
- 建議**每天備份**一次
- 重啟後需手動還原

### 還原時的行為

- 維護期間 LINE 訊息會收到「系統維護中」
- 訊息**不會被處理**（捨棄）
- 還原完成後自動恢復正常

### 自動備份建議

可使用外部排程服務（如 GitHub Actions）定期執行備份：

```yaml
# .github/workflows/backup.yml
name: Daily Backup
on:
  schedule:
    - cron: '0 0 * * *'  # 每天 UTC 00:00
jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Download backup
        run: |
          curl -H "X-API-Key: ${{ secrets.API_KEY }}" \
            https://your-app.onrender.com/api/db/download \
            -o backup_$(date +%Y%m%d).db
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: database-backup
          path: backup_*.db
```

---

## 更新紀錄

### rev3.1 (2025-12-26)
- ✅ 新增資料庫 Restore 功能
- ✅ 新增 Maintenance Mode
- ✅ 新增 Rollback 機制
- ✅ 新增 `/api/db/restore`, `/api/db/validate`, `/api/db/maintenance`
- ✅ 更新 `db_analyzer.py` 支援 `restore`, `validate`, `remote-stats`, `maintenance`

### rev3 (2025-12-25)
- SQLite 對話歷史記錄
- 同時記錄 User 和 AI 訊息

### rev2 (2025-12-25)
- google-genai SDK

### rev1 (2025-12-25)
- 初始模組化版本

---

更新日期：2025-12-26
