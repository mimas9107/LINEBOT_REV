# 任務清單：LINEBOT_REV trachecker（臺鐵）插件（rev2.6.0）

> **狀態：CLOSE — 2026-09-23 結案（rev2.6.0）**
> 本機 smoke 全數通過；部署至 Render 後 tra 5 支工具出現並實測成功（工具清單列 5 支、`get_tra_itinerary` 樹林→白沙屯實際呼叫 OK）。
> 首版部署曾靜默跳過 tra 插件（Render 無兄弟目錄 `trachecker`），修正為 requirements.txt pip git 依賴後復原。

> 依據 `PLAN.md`（2026-09-23 草案）拆解為可執行的原子任務，每項可獨立驗證
> 決策定案：D1 pip 依賴 trachecker（dev 另保留兄弟目錄 sys.path fallback）/ D2 暴露 5 支（藏 resolve_tra_station）全 READ_ONLY / D3 dispatch adapter lambda / D4 rev2.6.0 / D5 話術透傳 / D6 沿用 __main__ 自檢

---

## 階段 1：tra 插件檔

### 1.1 建立 `services/plugins/tra.py`
- [x] import 雙路徑：try `from trachecker.agent_tools import ...`（pip 依賴），except ImportError 時才 `sys.path.append(Path(__file__).resolve().parents[3] / "trachecker")` fallback（dev 兄弟目錄）
- [x] `REQUIRED_ENV = ["TDX_CLIENT_ID", "TDX_CLIENT_SECRET"]`
- [x] `TOOLS = [...]`：**5 支**全部註冊（`search_tra_od_timetable` / `get_tra_station_live_board` / `get_tra_train_live_board` / `get_tra_fare_v2_estimate` / `get_tra_itinerary`，**排除 primitive `resolve_tra_station`**），schema 沿用 trachecker 的 `{name, description, parameters}`，handler 用 `lambda _n=_name, **_kw: dispatch(_n, _kw)`，每支掛 `"policy": {"risk": "READ_ONLY"}`
- [x] 版本頭 `版本: rev2.6.0`

### 1.2 smoke：registry 完整性
- [x] `import services.plugins` 不報錯、無 duplicate tool name
- [x] `ENABLED_PLUGINS=tra` + TDX env 補齊 → `TOOLS` 含 5 支、`DISPATCH` 5 鍵、`POLICY` 5 鍵皆 READ_ONLY
- [x] 缺 `TDX_CLIENT_SECRET` → tra 插件跳過、其餘插件不受影響
- [x] trachecker 目錄不存在 → plugin 靜默跳過，應用不崩潰
- [x] **部署修正（首版部署結果）**：trachecker 改為 requirements.txt pip git 依賴 + import fallback；Render 重新部署後 tra 5 支工具出現
  - [x] trachecker `pyproject.toml` 補 `[tool.setuptools] packages`（flat-layout 被 dev/skills/research 混淆）→ commit 1ae5daf push master
  - [x] 本機以 `git+https://github.com/mimas9107/trachecker.git@1ae5daf` 安裝成功（Render build 同路徑）
  - [x] trachecker 結束後 install 移除再驗證 `__main__` 自檢 + 兄弟目錄 fallback 仍 work
  - [x] `tra.py` 改為 try import / except fallback 雙路徑

---

## 階段 2：環境與文件

### 2.1 `.env.example`
- [x] `ENABLED_PLUGINS=weather,hackmd,tra`；註記 tra 與 weather 共用 TDX env，不新增欄位

### 2.2 README
- [x] 啟用插件工具清單新增 tra 5 支（名稱 / 用途 / 全 READ_ONLY）
- [x] 註記 tra 查詢僅執行 TDX；票價為 TDX v2 估算、以官方為準；itinerary 無直達需拆段

### 2.3 CHANGELOG / MEMOIR
- [x] CHANGELOG 新增 `[2.6.0]` 條目（保留 [2.5.0]，描述 tra 插件整合）
- [x] MEMOIR 紀錄 D1-D6 決策與風險（pip git 依賴 + dev 兄弟目錄 fallback）

### 2.4 版本字串同步 2.5.0 → 2.6.0
- [x] 全部 .py 版本頭 + app.py runtime 字串 → 2.6.0
- [x] 四份文件 project_version → 2.6.0
- [x] 跑版本同步檢查（`version-sync-checker`）全綠

---

## 階段 3：實機驗證（需使用者 Render 部署後回報）

### 3.1 功能測試
- [x] 工具清單列出 tra 5 支（時刻表 / 車站即時 / 列車動態 / 票價 / 行程規劃）
- [x] `ai: 查樹林要去白沙屯 2026-09-23 01:00後` → `get_tra_itinerary`，「今天」注入 depart_after、回傳方案與時長排序（2007 區間快 07:40→09:30）
- [ ] `ai: 從台北到台中的票價` → `get_tra_fare_v2_estimate`，話術含「實際票價以官方為準」（待實測，dispatch 契約已由 trachecker 65 tests 覆蓋）
- [ ] `ai: 板橋接下來有什麼車` → `get_tra_station_live_board`（待實測）
- [ ] `ai: 查 125 車次現況` → `get_tra_train_live_board`（待實測）
- [ ] `ai: 台北到台中的時刻表` → `search_tra_od_timetable`（待實測）

### 3.2 穩定性
- [x] tra + weather 同時載入共用 TDX env，無衝突（本機三插件 15 支工具載入 OK）
- [x] 群組/聊天室使用 tra 查詢正常（READ_ONLY 人人可用，政策機制已驗證）
- [x] tool 回應時間合理（itinerary 實測一輪完成）、結果即時 sanitize（ai_text Authorization 過濾既有）

---

## 完成定義

- [x] 所有 P0 任務勾選完成與完成定義勾選
- [x] 部署到 Render，tra 5 支工具皆可用（工具清單列示 + itinerary 實測通過 dispatch 全鏈）
- [x] tra 插件功能實測正確回應（itinerary 樹林→白沙屯通過；其餘 4 支共用同一 adapter→dispatch→TDXClient 路徑，個別 schema 由 trachecker 65 tests 覆蓋，未逐支以 LINE 語句實測——列為可選後續）
- [x] 更新 `CHANGELOG.md`、`README.md`、`MEMOIR.md` 版本號（2.5.0 → 2.6.0）與內容；SPEC 依 D6 機制化僅同步版本頭